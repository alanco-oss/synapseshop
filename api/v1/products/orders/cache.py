"""Camada de cache-aside dos pedidos (Aula 8).

Concentra nomenclatura de chaves, TTL, contadores de eficacia (hit rate) e a
regra de invalidação ligada aos eventos de dominio. Nenhuma logica de cache
existe nos viewsets alem do orchestration definida em `buscar_ou_preencher`.
"""
import logging
import os

from django.core.cache import cache
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

CHAVE_LISTA = "pedidos:list"
CHAVE_DETALHES = "pedido:{pedido_id}"
PREFIXO_METRICAS = "cache:metricas:"

TTL_LISTA = int(os.getenv("REDIS_TTL_LISTA", 60))
TTL_DETALHES = int(os.getenv("REDIS_TTL_DETALHES", 300))

ENDPOINT_LISTA = "lista"
ENDPOINT_DETALHES = "detalhes"
ENDPOINTS = (ENDPOINT_LISTA, ENDPOINT_DETALHES)


def chave_lista():
    return CHAVE_LISTA


def chave_detalhes(pedido_id):
    return CHAVE_DETALHES.format(pedido_id=pedido_id)


def _cache(operacao, *args, **kwargs):
    try:
        return operacao(*args, **kwargs)
    except RedisError as erro:
        logger.warning(
            "cache=indisponivel operacao=%s erro=%s", operacao.__name__, erro
        )
        return None


def _preencher(chave, payload, ttl):
    """Grava no cache e devolve False quando o Redis esta indisponivel."""
    try:
        cache.set(chave, payload, ttl)
        return True
    except RedisError as erro:
        logger.warning("cache=indisponivel operacao=set chave=%s erro=%s", chave, erro)
        return False


def buscar_ou_preencher(chave, ttl, endpoint, carregar):
    """Padrao cache-aside: procura no cache e, no miss, preenche com `carregar`."""
    payload = _cache(cache.get, chave)
    if payload is not None:
        _contador(endpoint, "hits")
        logger.info(
            "cache=hit endpoint=%s chave=%s", endpoint, chave
        )
        return payload

    _contador(endpoint, "misses")
    logger.info("cache=miss endpoint=%s chave=%s", endpoint, chave)
    payload = carregar()
    if payload is not None and _preencher(chave, payload, ttl):
        logger.info(
            "cache=preenchido endpoint=%s chave=%s ttl=%ss", endpoint, chave, ttl
        )
    return payload


def _chave_metrica(endpoint, resultado):
    return f"{PREFIXO_METRICAS}{endpoint}:{resultado}"


def _contador(endpoint, resultado):
    chave = _chave_metrica(endpoint, resultado)
    try:
        cache.incr(chave)
    except ValueError:
        _cache(cache.set, chave, 1, timeout=None)
    except RedisError as erro:
        logger.warning("cache=indisponivel operacao=incr chave=%s erro=%s", chave, erro)


def metricas():
    """Eficacia do cache por endpoint (hit_rate = hits/lookups)."""
    resumo = {}
    for endpoint in ENDPOINTS:
        hits = _cache(cache.get, _chave_metrica(endpoint, "hits"), 0) or 0
        misses = _cache(cache.get, _chave_metrica(endpoint, "misses"), 0) or 0
        lookups = hits + misses
        resumo[endpoint] = {
            "hits": hits,
            "misses": misses,
            "lookups": lookups,
            "hit_rate": round(hits / lookups, 4) if lookups else 0.0,
        }
    return resumo


def invalidar_lista(evento):
    """Regra de invalidação dos eventos que alteram o conjunto de pedidos."""
    _cache(cache.delete, chave_lista())
    logger.info("evento=%s chave=%s acao=invalidate", evento, chave_lista())


def invalidar_pedido(pedido_id, evento="PedidoAtualizado"):
    """Regra de invalidação dos eventos que alteram um pedido especifico."""
    _cache(cache.delete, chave_detalhes(pedido_id))
    _cache(cache.delete, chave_lista())
    logger.info(
        "evento=%s pedido_id=%s chaves=%s,%s acao=invalidate",
        evento,
        pedido_id,
        chave_detalhes(pedido_id),
        chave_lista(),
    )
