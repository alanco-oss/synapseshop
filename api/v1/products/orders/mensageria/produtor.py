"""Produtor Kafka do evento ``PedidoCriado`` (Aula 9).

O Django e sincrono (WSGI/gunicorn), por isso o ``AIOKafkaProducer`` vive
num event loop proprio executado numa thread daemon de background. A funcao
``publicar_evento`` e a API sincrona usada pelas views: despacha a coroutine
de envio com ``run_coroutine_threadsafe`` e aguarda o resultado com timeout.

Se o broker estiver indisponivel a publicacao falha com degradacao graciosa
(alinhado com a politica do cache na Aula 8): o pedido ja foi persistido, o
log regista ``status=falha`` e o produtor e reiniciado na tentativa seguinte.
"""
import asyncio
import json
import logging
import os
import threading
import time

from aiokafka import AIOKafkaProducer

from orders.mensageria import metricas, topicos

logger = logging.getLogger("orders.mensageria")

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9094")
TIMEOUT_LIGACAO = float(os.getenv("KAFKA_TIMEOUT_LIGACAO", "5"))
TIMEOUT_PUBLICACAO = float(os.getenv("KAFKA_TIMEOUT_PUBLICACAO", "5"))

_bloqueio = threading.RLock()
_estado = {"loop": None, "produtor": None, "thread": None}


def _arrancar_loop():
    with _bloqueio:
        if _estado["thread"] is None:
            loop = asyncio.new_event_loop()

            def _rodar():
                asyncio.set_event_loop(loop)
                _estado["loop"] = loop
                loop.run_forever()

            thread = threading.Thread(
                target=_rodar, name="kafka-produtor-loop", daemon=True
            )
            thread.start()
            while not loop.is_running():
                time.sleep(0.01)
            _estado["thread"] = thread
        return _estado["loop"]


async def _parar(produtor):
    try:
        await produtor.stop()
    except Exception:
        pass


async def _criar_e_arrancar(bootstrap_servers):
    """Cria e arranca o produtor dentro do event loop (exigencia do aiokafka)."""
    produtor = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
    try:
        await produtor.start()
    except Exception:
        await _parar(produtor)
        raise
    return produtor


def _descartar_produtor():
    with _bloqueio:
        produtor = _estado["produtor"]
        loop = _estado["loop"]
        _estado["produtor"] = None
    if produtor is not None and loop is not None and loop.is_running():
        asyncio.run_coroutine_threadsafe(_parar(produtor), loop)


def _obter_produtor():
    with _bloqueio:
        if _estado["produtor"] is not None:
            return _estado["produtor"]
        loop = _arrancar_loop()
        _estado["produtor"] = asyncio.run_coroutine_threadsafe(
            _criar_e_arrancar(BOOTSTRAP_SERVERS), loop
        ).result(timeout=TIMEOUT_LIGACAO)
        return _estado["produtor"]


def publicar_evento(evento, topico=topicos.TOPICO_PEDIDO_CRIADO):
    """Publica o evento JSON na chave de idempotencia; devolve True no sucesso."""
    inicio = time.perf_counter()
    tipo = evento.get("event_type", "?")
    chave = evento.get("idempotency_key", "?")
    try:
        produtor = _obter_produtor()
        bruto = json.dumps(evento, ensure_ascii=False).encode("utf-8")
        asyncio.run_coroutine_threadsafe(
            produtor.send_and_wait(topico, value=bruto, key=chave.encode("utf-8")),
            _estado["loop"],
        ).result(timeout=TIMEOUT_PUBLICACAO)
    except Exception as erro:
        duracao_ms = (time.perf_counter() - inicio) * 1000
        metricas.registrar_publicacao("falha", duracao_ms)
        logger.error(
            "evento=%s acao=publicar status=falha topico=%s chave_idempotencia=%s "
            "erro=%s duracao_ms=%.1f",
            tipo,
            topico,
            chave,
            f"{type(erro).__name__}: {erro}" if str(erro) else type(erro).__name__,
            duracao_ms,
        )
        _descartar_produtor()
        return False

    duracao_ms = (time.perf_counter() - inicio) * 1000
    metricas.registrar_publicacao("sucesso", duracao_ms)
    logger.info(
        "evento=%s acao=publicar status=sucesso topico=%s pedido_id=%s "
        "chave_idempotencia=%s duracao_ms=%.1f",
        tipo,
        topico,
        evento.get("payload", {}).get("pedido_id"),
        chave,
        duracao_ms,
    )
    return True


def fechar():
    """Fecha o produtor (usado por scripts de um unico disparo)."""
    _descartar_produtor()
