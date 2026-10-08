"""Idempotencia por deduplicacao com TTL no Redis (Aula 9, reutilizada na Aula 11).

A reserva da chave usa ``cache.add`` (Redis ``SET NX EX``), que e atomica:
a primeira mensagem que chegar cria a chave com TTL e prossegue; qualquer
reentrega ou duplicado encontra a chave e e ignorada. A chave e a de negocio
(``pedido:{id}``, ver ``contrato.chave_idempotencia``), pelo que o TTL cobre
janela de reentrega do broker apos o evento original ter sido processado.

O parametro ``namespace`` separa as chaves por fluxo: ``pedido_criado``
(Aula 9) e ``pagamento_simulado`` (Aula 11), com o marcador ``:feito:``
que distingue duplicado de reprocessamento pendente.
"""
import logging
import os

from django.core.cache import cache
from redis.exceptions import RedisError

logger = logging.getLogger("orders.mensageria")

PREFIXO = "idempotency:pedido_criado"
NAMESPACE_PAGAMENTO = "idempotency:pagamento_simulado"
TTL_IDEMPOTENCIA = int(os.getenv("IDEMPOTENCY_TTL", 24 * 3600))


def chave(chave_idempotencia, namespace=PREFIXO):
    return f"{namespace}:{chave_idempotencia}"


def tentar_reservar(chave_idempotencia, event_id, namespace=PREFIXO):
    """Reserva a chave; devolve True na primeira execucao e False em duplicados.

    Se o Redis estiver indisponivel levanta ``RedisError``: sem dedupe nao ha
    garantia de idempotencia, por isso o consumidor trata o erro como falha de
    processamento (reentrega) em vez de ignorar silenciosamente.
    """
    return cache.add(
        chave(chave_idempotencia, namespace), event_id, timeout=TTL_IDEMPOTENCIA
    )


def reservar_com_log(chave_idempotencia, event_id, namespace=PREFIXO):
    """Camada fina de log em volta da reserva; repassa ``RedisError``."""
    try:
        reservada = tentar_reservar(chave_idempotencia, event_id, namespace)
    except RedisError as erro:
        logger.warning(
            "redis=indisponivel acao=dedupe chave_idempotencia=%s erro=%s",
            chave_idempotencia,
            erro,
        )
        raise
    return reservada


def concluir(chave_idempotencia, event_id, namespace=PREFIXO):
    """Marca o efeito colateral como concluido (Aula 11).

    Gravado depois de o processamento terminar, permite distinguir, numa
    reentrega que perdeu a reserva, entre ``duplicada`` (ja notificado) e
    ``reprocessar`` (falha no meio dos dois passos).
    """
    cache.set(
        f"{namespace}:feito:{chave_idempotencia}",
        event_id,
        timeout=TTL_IDEMPOTENCIA,
    )


def ja_concluido(chave_idempotencia, namespace=PREFIXO):
    """True quando o efeito colateral desta chave ja foi executado."""
    try:
        return bool(cache.get(f"{namespace}:feito:{chave_idempotencia}"))
    except RedisError as erro:
        # Sem Redis nao ha como saber; o reprocessamento e idempotente.
        logger.warning(
            "redis=indisponivel acao=verificar_conclusao chave_idempotencia=%s "
            "erro=%s",
            chave_idempotencia,
            erro,
        )
        return False
