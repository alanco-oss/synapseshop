"""Testes unitários da rota de monitorização (products/health.py)."""
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from redis.exceptions import RedisError

from products import health


class FakeSocket:
    """Fake de ``socket``: liga com sucesso ou falha com OSError."""

    def __init__(self, falhar=False):
        self.falhar = falhar

    def create_connection(self, endereco, timeout=None):
        if self.falhar:
            raise OSError("ligacao recusada")
        return nullcontext(SimpleNamespace(endereco=endereco, timeout=timeout))


class FakeRedis:
    """Fake de cache que falha sempre com RedisError."""

    def get(self, *args, **kwargs):
        raise RedisError("indisponivel")


class FakeLigacaoBD:
    """Fake de ``django.db.connection`` com ligação recusada."""

    def ensure_connection(self):
        raise RuntimeError("sem base de dados")


def _corpo(response):
    import json

    return json.loads(response.content)


@pytest.mark.django_db
def test_health_tudo_disponivel(api_client, monkeypatch):
    monkeypatch.setattr(health, "socket", FakeSocket())

    resposta = api_client.get("/health")

    assert resposta.status_code == 200
    assert _corpo(resposta) == {
        "status": "ok",
        "app": "synapseshop-api",
        "db": "ok",
        "redis": "ok",
        "kafka": "ok",
    }


@pytest.mark.django_db
def test_health_degradado_sem_redis(api_client, monkeypatch):
    monkeypatch.setattr(health, "cache", FakeRedis())
    monkeypatch.setattr(health, "socket", FakeSocket())

    resposta = api_client.get("/health")

    assert resposta.status_code == 200
    corpo = _corpo(resposta)
    assert corpo["status"] == "degraded"
    assert corpo["redis"] == "indisponivel"
    assert corpo["db"] == "ok"
    assert corpo["kafka"] == "ok"


@pytest.mark.django_db
def test_health_degradado_sem_kafka(api_client, monkeypatch):
    monkeypatch.setattr(health, "socket", FakeSocket(falhar=True))

    resposta = api_client.get("/health")

    assert resposta.status_code == 200
    corpo = _corpo(resposta)
    assert corpo["status"] == "degraded"
    assert corpo["kafka"] == "indisponivel"


@pytest.mark.django_db
def test_health_degradado_bootstrap_sem_porta(api_client, monkeypatch):
    monkeypatch.setattr(health, "BOOTSTRAP_SERVERS", "redpanda")

    resposta = api_client.get("/health")

    assert resposta.status_code == 200
    assert _corpo(resposta)["kafka"] == "indisponivel"


def test_health_erro_de_bd_devolve_503(api_client, monkeypatch):
    monkeypatch.setattr(health, "connection", FakeLigacaoBD())

    resposta = api_client.get("/health")

    assert resposta.status_code == 503
    corpo = _corpo(resposta)
    assert corpo["status"] == "error"
    assert corpo["db"] == "indisponivel"
