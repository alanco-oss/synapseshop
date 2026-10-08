"""Metricas acumuladas da mensageria no Redis (Aula 10).

Contadores e somas acumulados (sem TTL, para sobreviverem a reinicios) que
permitem, a partir do endpoint ``/api/v1/pedidos/metricas-mensageria/`` e dos
logs, analisar a latencia media e o throughput do fluxo ``PedidoCriado`` e os
trade-offs de dedupe (Redis SET NX EX) vs latencia vs throughput.

Chaves fisicas (com prefixo do Django): ``synapseshop:1:mensageria:metricas:*``.
O Redis indisponivel degrada para log (como o cache na Aula 8), nunca quebra a
publicacao nem o consumo.

Aula 11: acrescenta o contador ``notificacoes`` (e o desmembramento
``aprovado``/``recusado``) das notificacoes simuladas produzidas pelo worker
``consumir_pagamento``.
"""
import logging

from django.core.cache import cache
from redis.exceptions import RedisError

logger = logging.getLogger("orders.mensageria")

PREFIXO = "mensageria:metricas:"
PUBLICACOES = "publicacoes"
CONSUMO = "consumos"
DUPLICADOS = "duplicados"
DLQ = "dlq"
FALHAS_PUBLICACAO = "publicacoes_falhas"
NOTIFICACOES = "notificacoes"


def _incr(chave, delta=1):
    try:
        cache.incr(chave, delta)
    except ValueError:
        # Chave ainda nao existe. (SE)NX e atomico entre processos — so um
        # consumidor cria a chave; quem perder a corrida soma por cima.
        if not cache.add(chave, delta, timeout=None):
            cache.incr(chave, delta)
    except RedisError as erro:
        logger.warning("redis=indisponivel acao=metrica chave=%s erro=%s", chave, erro)


def _somar(chave, valor):
    delta = int(valor * 1000)
    try:
        cache.incr(chave, delta)
    except ValueError:
        if not cache.add(chave, delta, timeout=None):
            cache.incr(chave, delta)
    except RedisError as erro:
        logger.warning("redis=indisponivel acao=metrica chave=%s erro=%s", chave, erro)


def registrar_publicacao(resultado, duracao_ms):
    contador = PUBLICACOES if resultado == "sucesso" else FALHAS_PUBLICACAO
    _incr(f"{PREFIXO}{contador}")
    if resultado == "sucesso":
        _somar(f"{PREFIXO}publicacoes_duracao_ms", duracao_ms)


def registrar_consumo(duracao_ms, latencia_ms, duplicado=False, dlq=False):
    _incr(f"{PREFIXO}{CONSUMO}")
    _somar(f"{PREFIXO}consumos_duracao_ms", duracao_ms)
    if latencia_ms >= 0:
        _somar(f"{PREFIXO}consumos_latencia_ms", latencia_ms)
    if duplicado:
        _incr(f"{PREFIXO}{DUPLICADOS}")
    if dlq:
        _incr(f"{PREFIXO}{DLQ}")


def registrar_notificacao(resultado):
    """Conta notificacoes simuladas enviadas pelo worker (Aula 11)."""
    _incr(f"{PREFIXO}{NOTIFICACOES}")
    if resultado:
        _incr(f"{PREFIXO}notificacoes:{resultado}")


def resumo():
    """Media de duracao/latencia e throughput acumulados por etapa do fluxo."""
    def _ler(nome, padrao=0):
        try:
            return cache.get(f"{PREFIXO}{nome}", padrao) or padrao
        except RedisError as erro:
            logger.warning("redis=indisponivel acao=metrica chave=%s erro=%s", nome, erro)
            return padrao

    publicacoes = _ler("publicacoes")
    falhas = _ler("publicacoes_falhas")
    publicacoes_total = publicacoes + falhas
    consumos = _ler("consumos")
    duplicados = _ler("duplicados")
    dlq = _ler("dlq")
    publicacoes_ms = _ler("publicacoes_duracao_ms", 0.0)
    consumos_ms = _ler("consumos_duracao_ms", 0.0)
    latencia_ms = _ler("consumos_latencia_ms", 0.0)

    return {
        "produtor": {
            "publicacoes": publicacoes,
            "publicacoes_falhas": falhas,
            "publicacoes_total": publicacoes_total,
            "tempo_medio_ms": round(publicacoes_ms / publicacoes / 1000, 2)
            if publicacoes else 0.0,
            "tempo_total_ms": publicacoes_ms / 1000,
        },
        "consumidor": {
            "consumos": consumos,
            "duplicados": duplicados,
            "dlq": dlq,
            "falha_percentual": round(dlq / consumos * 100, 3) if consumos else 0.0,
            "duracao_media_ms": round(consumos_ms / consumos / 1000, 2)
            if consumos else 0.0,
            "latencia_media_ms": round(latencia_ms / consumos / 1000, 2)
            if consumos else 0.0,
            "duracao_total_ms": consumos_ms / 1000,
            "latencia_total_ms": latencia_ms / 1000,
        },
        "notificacoes": {
            "total": _ler("notificacoes"),
            "aprovados": _ler("notificacoes:aprovado"),
            "recusados": _ler("notificacoes:recusado"),
        },
    }