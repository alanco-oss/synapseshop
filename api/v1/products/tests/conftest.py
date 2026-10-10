"""Fixtures globais da suíte de testes (Aula 12).

Convenções da equipa:

- ``cache_teste`` (autouse): isola o cache em memória local (locmem) para que
  nenhum teste dependa do Redis e todos comecem com estado limpo;
- ``relogio_fixo``: congela o tempo em UTC para datetimes determinísticos;
- ``publicador_falso``: substitui o produtor Kafka por um fake que grava os
  eventos publicados numa lista, sem tocar em broker;
- ``fabrica_pedido``: payloads determinísticos (sem aleatoriedade) para que os
  testes sejam estáveis entre execuções.
"""
import os

import pytest
import requests
from django.core.cache import cache
from freezegun import freeze_time
from rest_framework.test import APIClient

import assist.llm_service as llm_service
from assist.circuit_breaker import INTERRUPTOR
from orders.mensageria import produtor, topicos

# Os testes dos workers patcham ``sync_to_async`` para correr na propria thread
# (a BD de teste vive na transacao do pytest-django), por isso o guard que
# proibe ORM em contexto async pode ser dispensado com seguranca.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")


@pytest.fixture
def api_client():
    """Cliente HTTP do DRF para os testes de integração."""
    return APIClient()


@pytest.fixture(autouse=True)
def cache_teste(settings):
    """BD efémera de cache: locmem no lugar do Redis, limpa à volta de cada teste."""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "synapseshop-testes",
        }
    }
    cache.clear()
    yield cache
    cache.clear()


@pytest.fixture
def relogio_fixo():
    """Relógio fixo (UTC) exigido pela spec para evitar testes intermitentes."""
    with freeze_time("2026-01-15T12:00:00") as congelado:
        yield congelado


@pytest.fixture
def publicador_falso(monkeypatch):
    """Fake do produtor Kafka: grava ``(evento, topico)`` e devolve ``True``."""
    publicados = []

    def _publicar(evento, topico=topicos.TOPICO_PEDIDO_CRIADO):
        publicados.append({"evento": evento, "topico": topico})
        return True

    monkeypatch.setattr(produtor, "publicar_evento", _publicar)
    return publicados


@pytest.fixture
def fabrica_pedido():
    """Payload determinístico de pedido: dados fixos, sem aleatoriedade."""

    def _fabricar(**campos):
        payload = {"user_id": 7, "total": "129.90"}
        payload.update(campos)
        return payload

    return _fabricar


@pytest.fixture
def provedor_falso(monkeypatch):
    """Fake do transporte HTTP: responde segundo a fila, sem tocar na rede."""
    fila = []
    registo = {"chamadas": 0, "payloads": [], "timeout": None}

    def _post(url, headers=None, json=None, timeout=None):
        registo["chamadas"] += 1
        registo["payloads"].append(json)
        registo["timeout"] = timeout
        if not fila:
            raise AssertionError("provedor_falso: fila de respostas vazia")
        acao = fila.pop(0)
        if isinstance(acao, Exception):
            raise acao
        return acao

    monkeypatch.setattr(llm_service.requests, "post", _post)
    return {"fila": fila, "registo": registo}


@pytest.fixture(autouse=True)
def interruptor_reset():
    """Circuit breaker isolado entre testes (estado em memória global)."""
    INTERRUPTOR.resetar()
    yield
    INTERRUPTOR.resetar()


@pytest.fixture
def sem_dormir(monkeypatch):
    """Backoff instantâneo: nenhum teste do assistente dorme durante o retry."""
    monkeypatch.setattr(llm_service.time, "sleep", lambda _: None)
