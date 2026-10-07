"""Idempotencia por deduplicacao com TTL no Redis (Aula 9).

A reserva da chave usa ``cache.add`` (Redis ``SET NX EX``), que e atomica:
a primeira mensagem que chegar cria a chave com TTL e prossegue; qualquer
reentrega ou duplicado encontra a chave e e ignorada. A chave e a de negocio
(``pedido:{id}``, ver ``contrato.chave_idempotencia``), pelo que o TTL cobre
janela de reentrega do broker apos o evento original ter sido processado.
"""
import logging
import os

from django.core.cache import cache
from redis.exceptions import RedisError

logger = logging.getLogger("orders.mensageria")

PREFIXO = "idempotency:pedido_criado"
TTL_IDEMPOTENCIA = int(os.getenv("IDEMPOTENCY_TTL", 24 * 3600))


def chave(chave_idempotencia):
    return f"{PREFIXO}:{chave_idempotencia}"


def tentar_reservar(chave_idempotencia, event_id):
    """Reserva a chave; devolve True na primeira execucao e False em duplicados.

    Se o Redis estiver indisponivel levanta ``RedisError``: sem dedupe nao ha
    garantia de idempotencia, por isso o consumidor trata o erro como falha de
    processamento (reentrega) em vez de ignorar silenciosamente.
    """
    return cache.add(chave(chave_idempotencia), event_id, timeout=TTL_IDEMPOTENCIA)


def reservar_com_log(chave_idempotencia, event_id):
    """Camada fina de log em volta da reserva; repassa ``RedisError``."""
    try:
        reservada = tentar_reservar(chave_idempotencia, event_id)
    except RedisError as erro:
        logger.warning(
            "redis=indisponivel acao=dedupe chave_idempotencia=%s erro=%s",
            chave_idempotencia,
            erro,
        )
        raise
    return reservada
