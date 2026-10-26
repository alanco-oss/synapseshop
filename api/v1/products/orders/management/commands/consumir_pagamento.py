"""Worker consumidor do evento ``PagamentoSimulado`` (Aula 11).

Corre como management command (``python manage.py consumir_pagamento``) no
servico ``worker-notificacoes`` do ``docker-compose``, separado do worker da
Aula 9/10 para nao alterar a semantica nem o ``--scale worker=3`` ja validados.

Garantias (mesmo desenho de ``consumir_pedido_criado``):

- **pelo menos uma vez**: commit manual so apos processar (ou encaminhar
  para DLQ);
- **idempotencia**: dedupe no Redis com namespace proprio
  (``idempotency:pagamento_simulado:pagamento:{id}``);
- **reentrega com recuo**: ``MENSAGERIA_TENTATIVAS`` com backoff exponencial;
- **DLQ**: ``pedidos.pagamento.dlq`` com headers ``x-error`` etc.;
- **metricas**: logs estruturados com ``duracao_ms``/``latencia_ms`` e
  contadores de notificacao no Redis.

Processamento: valida o contrato, garante a transicao ``pending -> paid``
quando aprovado (o evento e a fonte de verdade em reprocessamentos),
invalida o cache do pedido e emite a notificacao simulada (log
``acao=notificar``) — o "e" final do fluxo criar -> pagar -> notificar.
"""
import asyncio
import json
import logging
import os
import socket
import time
from datetime import UTC, datetime

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand

from orders import cache as cache_pedidos
from orders.mensageria import contrato, idempotencia, metricas, topicos
from orders.models import Order

logger = logging.getLogger("orders.mensageria")

GRUPO_CONSUMIDOR = "synapseshop-pagamentos"
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9094")
N_TENTATIVAS = int(os.getenv("MENSAGERIA_TENTATIVAS", "5"))
BACKOFF_BASE = float(os.getenv("MENSAGERIA_BACKOFF_BASE", "0.5"))
BACKOFF_MAXIMO = float(os.getenv("MENSAGERIA_BACKOFF_MAXIMO", "8"))
FORCAR_FALHA = os.getenv("MENSAGERIA_FORCAR_FALHA") == "1"


def _latencia_ms(mensagem):
    """Ocorrencia -> consumacao em ms; -1 quando o payload nao e analisavel."""
    try:
        evento = json.loads(mensagem.value)
        ocorrido = datetime.fromisoformat(evento["occurred_at"])
        return (
            datetime.now(UTC) - ocorrido
        ).total_seconds() * 1000
    except Exception:
        return -1.0


def _descrever_erro(erro):
    return f"{type(erro).__name__}: {erro}" if str(erro) else type(erro).__name__


def _notificar(evento):
    """Garante o estado do pedido, invalida o cache e emite a notificacao.

    E chamado dentro de ``sync_to_async`` (acesso a ORM/cache sincronos).
    """
    payload = evento["payload"]
    pedido = Order.objects.get(pk=payload["pedido_id"])
    aprovado = payload["aprovado"]

    if aprovado and pedido.status != "paid":
        pedido.status = "paid"
        pedido.save(update_fields=["status"])

    cache_pedidos.invalidar_pedido(
        pedido.pk, "PagamentoSimulado" if aprovado else "PagamentoRecusado"
    )

    resultado = "aprovado" if aprovado else "recusado"
    canal = "email"  # canal simulado — sem envio real (fora do escopo)
    logger.info(
        "evento=PagamentoSimulado pedido_id=%s user_id=%s total=%s "
        "acao=notificar canal=%s resultado=%s status=%s "
        "chave_idempotencia=%s",
        pedido.pk,
        pedido.user_id,
        payload["total"],
        canal,
        resultado,
        pedido.status,
        evento["idempotency_key"],
    )
    metricas.registrar_notificacao(resultado)
    return resultado


async def processar(mensagem):
    """Processa uma mensagem; devolve ``novo``, ``duplicada`` ou levanta erro."""
    if FORCAR_FALHA:
        raise RuntimeError("falha_forcada=MENSAGERIA_FORCAR_FALHA")
    if not mensagem.value:
        raise ValueError("mensagem_vazia")

    try:
        evento = json.loads(mensagem.value)
    except json.JSONDecodeError as erro:
        raise ValueError(f"json_invalido={erro}") from erro

    contrato.validar_pagamento(evento)
    chave = evento["idempotency_key"]
    pedido_id = evento["payload"]["pedido_id"]

    reservada = await sync_to_async(idempotencia.reservar_com_log)(
        chave, evento["event_id"], idempotencia.NAMESPACE_PAGAMENTO
    )
    if not reservada:
        # Reserva ja existente: se a notificacao ja foi emitida, e duplicado;
        # caso contrario (falha entre reservar e notificar) reprocessa.
        concluido = await sync_to_async(idempotencia.ja_concluido)(
            chave, idempotencia.NAMESPACE_PAGAMENTO
        )
        if concluido:
            logger.info(
                "evento=PagamentoSimulado pedido_id=%s chave_idempotencia=%s "
                "acao=processar dedupe=duplicada",
                pedido_id,
                chave,
            )
            return "duplicada"

    resultado = await sync_to_async(_notificar)(evento)
    await sync_to_async(idempotencia.concluir)(
        chave, evento["event_id"], idempotencia.NAMESPACE_PAGAMENTO
    )
    logger.info(
        "evento=PagamentoSimulado pedido_id=%s chave_idempotencia=%s "
        "acao=processar dedupe=novo resultado=%s",
        pedido_id,
        chave,
        resultado,
    )
    return "novo"


class Command(BaseCommand):
    help = (
        "Consome eventos PagamentoSimulado do Kafka e emite a notificacao "
        "simulada (idempotencia, retry/backoff e DLQ)"
    )

    def handle(self, *args, **options):
        asyncio.run(self._consumir())

    async def _arrancar(self, fabrica, nome):
        atraso = 1.0
        while True:
            instancia = fabrica()
            try:
                await instancia.start()
                return instancia
            except Exception as erro:
                await self._parar_em_silencio(instancia)
                logger.warning(
                    "kafka=indisponivel acao=arrancar componente=%s erro=%s "
                    "proxima_tentativa_em=%.1fs",
                    nome,
                    erro,
                    atraso,
                )
                await asyncio.sleep(atraso)
                atraso = min(atraso * 2, 10)

    @staticmethod
    async def _parar_em_silencio(instancia):
        try:
            await instancia.stop()
        except Exception:
            pass

    async def _consumir(self):
        await topicos.garantir_com_retry()
        consumidor = await self._arrancar(
            lambda: AIOKafkaConsumer(
                topicos.TOPICO_PAGAMENTO,
                bootstrap_servers=BOOTSTRAP_SERVERS,
                group_id=GRUPO_CONSUMIDOR,
                enable_auto_commit=False,
                auto_offset_reset="earliest",
            ),
            "consumidor",
        )
        produtor_dlq = await self._arrancar(
            lambda: AIOKafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS),
            "produtor_dlq",
        )
        logger.info(
            "evento=PagamentoSimulado acao=arrancar worker topico=%s dlq=%s "
            "grupo=%s bootstrap=%s tentativas=%d backoff_base=%.1fs "
            "backoff_max=%.1fs forcar_falha=%s worker_id=%s",
            topicos.TOPICO_PAGAMENTO,
            topicos.TOPICO_PAGAMENTO_DLQ,
            GRUPO_CONSUMIDOR,
            BOOTSTRAP_SERVERS,
            N_TENTATIVAS,
            BACKOFF_BASE,
            BACKOFF_MAXIMO,
            FORCAR_FALHA,
            WORKER_ID,
        )
        try:
            async for mensagem in consumidor:
                await self._tratar(consumidor, produtor_dlq, mensagem)
        finally:
            await self._parar_em_silencio(produtor_dlq)
            await self._parar_em_silencio(consumidor)

    async def _tratar(self, consumidor, produtor_dlq, mensagem):
        inicio = time.perf_counter()
        tentativa = 0
        duracao_ms = latencia_ms = 0.0
        while True:
            tentativa += 1
            try:
                desfecho = await processar(mensagem)
                await consumidor.commit()
                duracao_ms = (time.perf_counter() - inicio) * 1000
                latencia_ms = _latencia_ms(mensagem)
                metricas.registrar_consumo(
                    duracao_ms, latencia_ms, duplicado=desfecho == "duplicada"
                )
                logger.info(
                    "evento=PagamentoSimulado acao=consumir status=sucesso "
                    "desfecho=%s tentativas=%d duracao_ms=%.1f "
                    "latencia_ms=%.1f particao=%d offset=%d worker_id=%s",
                    desfecho,
                    tentativa,
                    duracao_ms,
                    latencia_ms,
                    mensagem.partition,
                    mensagem.offset,
                    WORKER_ID,
                )
                return
            except Exception as erro:
                if tentativa >= N_TENTATIVAS:
                    try:
                        await self._enviar_dlq(produtor_dlq, mensagem, erro, tentativa)
                        await consumidor.commit()
                    except Exception as falha_dlq:
                        # Sem commit, a mensagem fica por confirmada e o worker
                        # (restart: on-failure) reprocessa-a no arranque.
                        logger.critical(
                            "evento=PagamentoSimulado acao=dlq status=falha erro=%s",
                            _descrever_erro(falha_dlq),
                            exc_info=True,
                        )
                        raise
                    duracao_ms = (time.perf_counter() - inicio) * 1000
                    latencia_ms = _latencia_ms(mensagem)
                    metricas.registrar_consumo(duracao_ms, latencia_ms, dlq=True)
                    logger.error(
                        "evento=PagamentoSimulado acao=consumir status=dlq "
                        "tentativas=%d erro=%s duracao_ms=%.1f latencia_ms=%.1f "
                        "particao=%d offset=%d worker_id=%s",
                        tentativa,
                        _descrever_erro(erro),
                        duracao_ms,
                        latencia_ms,
                        mensagem.partition,
                        mensagem.offset,
                        WORKER_ID,
                    )
                    return
                atraso = min(BACKOFF_BASE * (2 ** (tentativa - 1)), BACKOFF_MAXIMO)
                logger.warning(
                    "evento=PagamentoSimulado acao=consumir status=falha "
                    "tentativa=%d/%d erro=%s proxima_reentrega_em=%.1fs "
                    "particao=%d offset=%d worker_id=%s",
                    tentativa,
                    N_TENTATIVAS,
                    _descrever_erro(erro),
                    atraso,
                    mensagem.partition,
                    mensagem.offset,
                    WORKER_ID,
                )
                await asyncio.sleep(atraso)

    @staticmethod
    async def _enviar_dlq(produtor_dlq, mensagem, erro, tentativas):
        cabecalhos = [
            ("x-error", _descrever_erro(erro).encode("utf-8", "replace")[:512]),
            ("x-tentativas", str(tentativas).encode("utf-8")),
            ("x-topico-original", topicos.TOPICO_PAGAMENTO.encode("utf-8")),
            ("x-particao", str(mensagem.partition).encode("utf-8")),
            ("x-offset", str(mensagem.offset).encode("utf-8")),
        ]
        await produtor_dlq.send_and_wait(
            topicos.TOPICO_PAGAMENTO_DLQ,
            value=mensagem.value,
            key=mensagem.key,
            headers=cabecalhos,
        )
