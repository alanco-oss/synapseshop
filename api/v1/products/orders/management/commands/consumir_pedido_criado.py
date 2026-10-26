"""Worker consumidor do evento ``PedidoCriado`` (Aula 9).

Corre como management command (``python manage.py consumir_pedido_criado``)
para herdar settings, variaveis de ambiente e logging do proprio projeto.

Garantias:

- **pelo menos uma vez**: ``enable_auto_commit=False`` e commit manual apenas
  apos o processamento (ou a encaminhamento para DLQ) terminar;
- **idempotencia**: dedupe no Redis via ``idempotencia.reservar_com_log``
  (chave de negocio ``pedido:{id}`` com TTL) antes de persistir;
- **reentrega com recuo**: ``MENSAGERIA_TENTATIVAS`` tentativas com backoff
  exponencial ``BACKOFF_BASE * 2**(n-1)``, limitado por ``BACKOFF_MAXIMO``;
- **DLQ**: esgotadas as tentativas, a mensagem original e reencaminhada para
  ``pedidos.criado.dlq`` com headers ``x-error``, ``x-tentativas`` etc. e so
  entao o offset e confirmado;
- **metricas**: logs estruturados ``acao=consumir`` com ``duracao_ms`` (tempo
  de processamento) e ``latencia_ms`` (ocorrencia -> consumacao), alem de
  contadores acumulados no Redis via ``metricas``.

Aula 10: no arranque garante a configuracao dos topicos (particoes e retencao
via ``topicos.garantir_com_retry``) e os logs transportam ``particao``,
``offset`` e ``worker_id`` para observar o paralelismo por particoes — varias
instancias deste comando no mesmo grupo (``docker compose up --scale
worker=3``) repartem as particoes automaticamente por rebalance.

Simulacao de erro forcado: ``MENSAGERIA_FORCAR_FALHA=1`` faz toda a
processamento falhar de proposito, para validar o caminho ate a DLQ.
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
from django.utils import timezone as django_timezone

from orders.mensageria import contrato, idempotencia, metricas, topicos
from orders.models import Order

logger = logging.getLogger("orders.mensageria")

GRUPO_CONSUMIDOR = "synapseshop-pedidos-criado"
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9094")
N_TENTATIVAS = int(os.getenv("MENSAGERIA_TENTATIVAS", "5"))
BACKOFF_BASE = float(os.getenv("MENSAGERIA_BACKOFF_BASE", "0.5"))
BACKOFF_MAXIMO = float(os.getenv("MENSAGERIA_BACKOFF_MAXIMO", "8"))
FORCAR_FALHA = os.getenv("MENSAGERIA_FORCAR_FALHA") == "1"
TIMEOUT_LIGACAO = float(os.getenv("KAFKA_TIMEOUT_LIGACAO", "5"))


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


def _persistir_pedido(pedido_id):
    pedido = Order.objects.get(pk=pedido_id)
    pedido.evento_criado_em = django_timezone.now()
    pedido.save(update_fields=["evento_criado_em"])
    return pedido


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

    contrato.validar(evento)
    chave = evento["idempotency_key"]
    pedido_id = evento["payload"]["pedido_id"]

    reservada = await sync_to_async(idempotencia.reservar_com_log)(
        chave, evento["event_id"]
    )
    if not reservada:
        # Se a reserva anterior existe mas o pedido nao foi persistido, a
        # tentativa falhou entre reservar e gravar: continua o processamento.
        ja_processado = await sync_to_async(
            lambda: Order.objects.filter(
                pk=pedido_id, evento_criado_em__isnull=False
            ).exists()
        )()
        if ja_processado:
            logger.info(
                "evento=PedidoCriado pedido_id=%s chave_idempotencia=%s "
                "acao=processar dedupe=duplicada",
                pedido_id,
                chave,
            )
            return "duplicada"

    await sync_to_async(_persistir_pedido)(pedido_id)
    logger.info(
        "evento=PedidoCriado pedido_id=%s chave_idempotencia=%s acao=processar "
        "dedupe=novo status=persistido",
        pedido_id,
        chave,
    )
    return "novo"


class Command(BaseCommand):
    help = "Consome eventos PedidoCriado do Kafka (idempotencia, retry/backoff e DLQ)"

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
                topicos.TOPICO_PEDIDO_CRIADO,
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
            "evento=PedidoCriado acao=arrancar worker topico=%s dlq=%s grupo=%s "
            "bootstrap=%s tentativas=%d backoff_base=%.1fs backoff_max=%.1fs "
            "forcar_falha=%s worker_id=%s",
            topicos.TOPICO_PEDIDO_CRIADO,
            topicos.TOPICO_DLQ,
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
                    "evento=PedidoCriado acao=consumir status=sucesso desfecho=%s "
                    "tentativas=%d duracao_ms=%.1f latencia_ms=%.1f "
                    "particao=%d offset=%d worker_id=%s",
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
                        # Sem commit, a mensagem fica por confirmar e o worker
                        # (restart: on-failure) reprocessa-a no arranque.
                        logger.critical(
                            "evento=PedidoCriado acao=dlq status=falha erro=%s",
                            _descrever_erro(falha_dlq),
                            exc_info=True,
                        )
                        raise
                    duracao_ms = (time.perf_counter() - inicio) * 1000
                    latencia_ms = _latencia_ms(mensagem)
                    metricas.registrar_consumo(
                        duracao_ms, latencia_ms, dlq=True
                    )
                    logger.error(
                        "evento=PedidoCriado acao=consumir status=dlq "
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
                    "evento=PedidoCriado acao=consumir status=falha tentativa=%d/%d "
                    "erro=%s proxima_reentrega_em=%.1fs particao=%d offset=%d "
                    "worker_id=%s",
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
            ("x-topico-original", topicos.TOPICO_PEDIDO_CRIADO.encode("utf-8")),
            ("x-particao", str(mensagem.partition).encode("utf-8")),
            ("x-offset", str(mensagem.offset).encode("utf-8")),
        ]
        await produtor_dlq.send_and_wait(
            topicos.TOPICO_DLQ, value=mensagem.value, key=mensagem.key, headers=cabecalhos
        )
