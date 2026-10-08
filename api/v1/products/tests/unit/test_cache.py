"""Testes unitários da camada de cache-aside (orders/cache.py)."""
import pytest
from redis.exceptions import RedisError

from orders import cache as cache_pedidos


class RedisIndisponivel:
    """Fake do Redis que falha sempre com RedisError."""

    def get(self, *args, **kwargs):
        raise RedisError("indisponivel")

    def set(self, *args, **kwargs):
        raise RedisError("indisponivel")

    def incr(self, *args, **kwargs):
        raise RedisError("indisponivel")

    def delete(self, *args, **kwargs):
        raise RedisError("indisponivel")


def test_chave_lista_e_constante():
    assert cache_pedidos.chave_lista() == "pedidos:list"


@pytest.mark.parametrize(
    "pedido_id,esperada",
    [
        (1, "pedido:1"),
        (42, "pedido:42"),
        ("abc", "pedido:abc"),
        (0, "pedido:0"),
    ],
)
def test_chave_detalhes(pedido_id, esperada):
    assert cache_pedidos.chave_detalhes(pedido_id) == esperada


def test_buscar_ou_preencher_hit_nao_chama_carregador(cache_teste):
    cache_teste.set(cache_pedidos.chave_lista(), [{"id": 1}], 60)
    chamadas = []

    def carregar():
        chamadas.append(1)
        return [{"id": 2}]

    dados = cache_pedidos.buscar_ou_preencher(
        cache_pedidos.chave_lista(), 60, cache_pedidos.ENDPOINT_LISTA, carregar
    )

    assert dados == [{"id": 1}]
    assert chamadas == []


def test_buscar_ou_preencher_miss_preenche_cache(cache_teste):
    chamadas = []

    def carregar():
        chamadas.append(1)
        return [{"id": 7}]

    dados = cache_pedidos.buscar_ou_preencher(
        "pedido:7", 60, cache_pedidos.ENDPOINT_DETALHES, carregar
    )

    assert dados == [{"id": 7}]
    assert chamadas == [1]
    assert cache_teste.get("pedido:7") == [{"id": 7}]


def test_buscar_ou_preencher_miss_sem_payload_nao_grava(cache_teste):
    dados = cache_pedidos.buscar_ou_preencher(
        "pedido:vazio", 60, cache_pedidos.ENDPOINT_DETALHES, lambda: None
    )

    assert dados is None
    assert cache_teste.get("pedido:vazio") is None


def test_buscar_ou_preencher_redis_indisponivel_degrada(monkeypatch):
    monkeypatch.setattr(cache_pedidos, "cache", RedisIndisponivel())

    dados = cache_pedidos.buscar_ou_preencher(
        "pedido:9", 60, cache_pedidos.ENDPOINT_DETALHES, lambda: {"id": 9}
    )

    assert dados == {"id": 9}


@pytest.mark.parametrize("endpoint", list(cache_pedidos.ENDPOINTS))
def test_metricas_zeradas_sem_lookups(cache_teste, endpoint):
    resumo = cache_pedidos.metricas()

    assert resumo[endpoint] == {
        "hits": 0,
        "misses": 0,
        "lookups": 0,
        "hit_rate": 0.0,
    }


def test_metricas_calcula_hit_rate(cache_teste):
    cache_pedidos.buscar_ou_preencher(
        "chave", 60, cache_pedidos.ENDPOINT_LISTA, lambda: None
    )
    cache_pedidos.buscar_ou_preencher(
        "chave", 60, cache_pedidos.ENDPOINT_LISTA, lambda: None
    )
    cache_teste.set("chave", "valor", 60)
    cache_pedidos.buscar_ou_preencher(
        "chave", 60, cache_pedidos.ENDPOINT_LISTA, lambda: None
    )

    resumo = cache_pedidos.metricas()[cache_pedidos.ENDPOINT_LISTA]

    assert resumo["hits"] == 1
    assert resumo["misses"] == 2
    assert resumo["lookups"] == 3
    assert resumo["hit_rate"] == 0.3333


def test_invalidar_lista_remove_chave(cache_teste):
    cache_teste.set(cache_pedidos.chave_lista(), [{"id": 1}], 60)

    cache_pedidos.invalidar_lista("PedidoCriado")

    assert cache_teste.get(cache_pedidos.chave_lista()) is None


def test_invalidar_pedido_remove_detalhe_e_lista(cache_teste):
    cache_teste.set(cache_pedidos.chave_detalhes(5), {"id": 5}, 60)
    cache_teste.set(cache_pedidos.chave_lista(), [{"id": 5}], 60)

    cache_pedidos.invalidar_pedido(5, "PagamentoAprovado")

    assert cache_teste.get(cache_pedidos.chave_detalhes(5)) is None
    assert cache_teste.get(cache_pedidos.chave_lista()) is None


@pytest.mark.parametrize(
    "operacao", ["invalidar_lista", "invalidar_pedido", "metricas"]
)
def test_cache_indisponivel_nao_quebra(monkeypatch, operacao):
    monkeypatch.setattr(cache_pedidos, "cache", RedisIndisponivel())

    if operacao == "invalidar_lista":
        cache_pedidos.invalidar_lista("PedidoCriado")
    elif operacao == "invalidar_pedido":
        cache_pedidos.invalidar_pedido(1)
    else:
        assert cache_pedidos.metricas()["lista"]["hits"] == 0
