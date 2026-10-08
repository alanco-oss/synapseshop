"""Rota ``GET /health`` para monitorizacao (Aula 3, reforcada na Aula 11).

Verifica as tres dependencias do mini-backend sem bloquear o arranque:

- **db** (obrigatorio): ``connection.ensure_connection``; falha devolve
  ``503`` porque sem banco nao ha fluxo de negocio;
- **redis** e **kafka** (opcionais): a API degrada graciosamente sem eles
  (Aulas 8/9), por isso a indisponibilidade marca ``status=degraded`` e
  mantem ``200`` — o ``HEALTHCHECK`` do Docker continua a refletir a
  saude real da aplicacao.

Resposta (formato ``key=value`` alinhado com os logs estruturados)::

    {"status": "ok", "app": "synapseshop-api", "db": "ok",
     "redis": "ok", "kafka": "ok"}
"""
import os
import socket

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from redis.exceptions import RedisError

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9094")
TIMEOUT_KAFKA = float(os.getenv("HEALTH_TIMEOUT_KAFKA", "1"))


def _verificar_db():
    connection.ensure_connection()
    return "ok"


def _verificar_redis():
    try:
        cache.get("healthcheck")
        return "ok"
    except RedisError:
        return "indisponivel"


def _verificar_kafka():
    """Teste de alcancabilidade do broker por TCP (sem consumir mensagens)."""
    primeiro = BOOTSTRAP_SERVERS.split(",")[0].strip()
    if ":" not in primeiro:
        return "indisponivel"
    host, porta = primeiro.rsplit(":", 1)
    try:
        with socket.create_connection((host, int(porta)), timeout=TIMEOUT_KAFKA):
            return "ok"
    except OSError:
        return "indisponivel"


def health(request):
    detalhe = {"app": "synapseshop-api"}

    try:
        detalhe["db"] = _verificar_db()
    except Exception:
        detalhe["db"] = "indisponivel"
        return JsonResponse(
            {"status": "error", **detalhe}, status=503
        )

    detalhe["redis"] = _verificar_redis()
    detalhe["kafka"] = _verificar_kafka()

    degradado = "indisponivel" in (detalhe["redis"], detalhe["kafka"])
    return JsonResponse({"status": "degraded" if degradado else "ok", **detalhe})
