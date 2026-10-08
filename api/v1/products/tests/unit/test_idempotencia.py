"""Testes unitários da idempotência (orders/mensageria/idempotencia.py)."""
import pytest
from redis.exceptions import RedisError

from orders.mensageria import idempotencia


class RedisIndisponivel:
    """Fake do Redis que falha sempre com RedisError."""

    def add(self, *args, **kwargs):
        raise RedisError("indisponivel")

    def set(self, *args, **kwargs):
        raise RedisError("indisponivel")

    def get(self, *args, **kwargs):
        raise RedisError("indisponivel")


@pytest.mark.parametrize(
    "chave_id,evento",
    [
        ("pedido:1", "aaaa-1111"),
        ("pedido:42", "bbbb-2222"),
        ("pagamento:7", "cccc-3333"),
    ],
)
def test_primeira_reserva_e_sempre_verdadeira(cache_teste, chave_id, evento):
    assert idempotencia.tentar_reservar(chave_id, evento) is True


def test_duplicado_e_rejeitado(cache_teste):
    assert idempotencia.tentar_reservar("pedido:1", "event-1") is True
    assert idempotencia.tentar_reservar("pedido:1", "event-2") is False


@pytest.mark.parametrize("namespace", [idempotencia.PREFIXO, idempotencia.NAMESPACE_PAGAMENTO])
def test_namespaces_sao_independentes(cache_teste, namespace):
    assert idempotencia.tentar_reservar("pedido:1", "e1", namespace=namespace) is True
    assert idempotencia.tentar_reservar("pedido:1", "e2", namespace=namespace) is False


def test_chave_inclui_namespace_e_marcador_de_conclusao():
    assert idempotencia.chave("pedido:9") == f"{idempotencia.PREFIXO}:pedido:9"
    assert idempotencia.chave("pedido:9", idempotencia.NAMESPACE_PAGAMENTO) == (
        f"{idempotencia.NAMESPACE_PAGAMENTO}:pedido:9"
    )


def test_concluir_e_verificado_por_ja_concluido(cache_teste):
    assert idempotencia.ja_concluido("pedido:3") is False

    idempotencia.concluir("pedido:3", "event-3")

    assert idempotencia.ja_concluido("pedido:3") is True


def test_concluir_namespace_pagamento(cache_teste):
    idempotencia.concluir("pedido:3", "event-3", namespace=idempotencia.NAMESPACE_PAGAMENTO)

    assert (
        idempotencia.ja_concluido("pedido:3", namespace=idempotencia.NAMESPACE_PAGAMENTO)
        is True
    )
    assert idempotencia.ja_concluido("pedido:3") is False


def test_reservar_com_log_repassa_erro(monkeypatch):
    monkeypatch.setattr(idempotencia, "cache", RedisIndisponivel())

    with pytest.raises(RedisError):
        idempotencia.reservar_com_log("pedido:1", "event-1")


def test_reservar_com_log_devolve_true_na_primeira(cache_teste):
    assert idempotencia.reservar_com_log("pedido:1", "event-1") is True
    assert idempotencia.reservar_com_log("pedido:1", "event-2") is False


def test_ja_concluido_com_redis_indisponivel_devolve_falso(monkeypatch):
    monkeypatch.setattr(idempotencia, "cache", RedisIndisponivel())

    assert idempotencia.ja_concluido("pedido:1") is False
