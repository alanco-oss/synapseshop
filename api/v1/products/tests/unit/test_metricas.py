"""Testes unitários das métricas de mensageria (orders/mensageria/metricas.py)."""
import pytest
from redis.exceptions import RedisError

from orders.mensageria import metricas


class RedisIndisponivel:
    """Fake do Redis que falha sempre com RedisError."""

    def incr(self, *args, **kwargs):
        raise RedisError("indisponivel")

    def add(self, *args, **kwargs):
        raise RedisError("indisponivel")

    def get(self, *args, **kwargs):
        raise RedisError("indisponivel")


def test_resumo_zerado_sem_registos(cache_teste):
    resumo = metricas.resumo()

    assert resumo["produtor"]["publicacoes"] == 0
    assert resumo["produtor"]["tempo_medio_ms"] == 0.0
    assert resumo["consumidor"]["consumos"] == 0
    assert resumo["consumidor"]["falha_percentual"] == 0.0
    assert resumo["notificacoes"] == {"total": 0, "aprovados": 0, "recusados": 0}


@pytest.mark.parametrize("duracao_ms", [2000, 250, 0])
def test_registrar_publicacao_sucesso_calcula_media(cache_teste, duracao_ms):
    metricas.registrar_publicacao("sucesso", duracao_ms)
    metricas.registrar_publicacao("sucesso", duracao_ms)

    produtor = metricas.resumo()["produtor"]

    assert produtor["publicacoes"] == 2
    assert produtor["publicacoes_falhas"] == 0
    assert produtor["publicacoes_total"] == 2
    assert produtor["tempo_medio_ms"] == pytest.approx(duracao_ms)
    assert produtor["tempo_total_ms"] == pytest.approx(duracao_ms * 2)


def test_registrar_publicacao_falha_nao_conta_duracao(cache_teste):
    metricas.registrar_publicacao("falha", 999.9)

    produtor = metricas.resumo()["produtor"]

    assert produtor["publicacoes"] == 0
    assert produtor["publicacoes_falhas"] == 1
    assert produtor["publicacoes_total"] == 1
    assert produtor["tempo_total_ms"] == 0


def test_registrar_consumo_agrega_duracao_e_latencia(cache_teste):
    metricas.registrar_consumo(duracao_ms=1000, latencia_ms=500)
    metricas.registrar_consumo(duracao_ms=3000, latencia_ms=1500)

    consumidor = metricas.resumo()["consumidor"]

    assert consumidor["consumos"] == 2
    assert consumidor["duracao_media_ms"] == pytest.approx(2000.0)
    assert consumidor["latencia_media_ms"] == pytest.approx(1000.0)
    assert consumidor["duracao_total_ms"] == pytest.approx(4000.0)
    assert consumidor["latencia_total_ms"] == pytest.approx(2000.0)


def test_registrar_consumo_latencia_negativa_e_ignorada(cache_teste):
    metricas.registrar_consumo(duracao_ms=100, latencia_ms=-1)

    consumidor = metricas.resumo()["consumidor"]

    assert consumidor["consumos"] == 1
    assert consumidor["latencia_total_ms"] == 0


def test_registrar_consumo_conta_duplicados_e_dlq(cache_teste):
    metricas.registrar_consumo(duracao_ms=10, latencia_ms=5, duplicado=True)
    metricas.registrar_consumo(duracao_ms=10, latencia_ms=5, dlq=True)

    consumidor = metricas.resumo()["consumidor"]

    assert consumidor["duplicados"] == 1
    assert consumidor["dlq"] == 1
    assert consumidor["falha_percentual"] == pytest.approx(50.0)


@pytest.mark.parametrize("resultado", ["aprovado", "recusado"])
def test_registrar_notificacao_por_resultado(cache_teste, resultado):
    metricas.registrar_notificacao(resultado)
    metricas.registrar_notificacao(resultado)

    notificacoes = metricas.resumo()["notificacoes"]

    assert notificacoes["total"] == 2
    assert notificacoes[f"{resultado}s"] == 2


def test_registrar_notificacao_sem_resultado_so_conta_total(cache_teste):
    metricas.registrar_notificacao(None)

    notificacoes = metricas.resumo()["notificacoes"]

    assert notificacoes["total"] == 1
    assert notificacoes["aprovados"] == 0
    assert notificacoes["recusados"] == 0


class CacheCorrida:
    """Simula a corrida atomica: o ``add`` perde mas a chave ja existe."""

    def __init__(self):
        self.valores = {}
        self.corridas = 0

    def incr(self, chave, delta=1):
        if chave not in self.valores:
            raise ValueError("chave inexistente")
        self.valores[chave] += delta

    def add(self, chave, valor, timeout=None):
        if chave in self.valores:
            return False
        if self.corridas < 1:
            # outro processo criou a chave primeiro: devolve False mas a chave passa a existir
            self.corridas += 1
            self.valores[chave] = valor
            return False
        self.valores[chave] = valor
        return True


def test_incr_com_corrida_soma_por_cima(monkeypatch):
    monkeypatch.setattr(metricas, "cache", CacheCorrida())

    metricas._incr("mensageria:metricas:corrida")

    assert metricas.cache.valores["mensageria:metricas:corrida"] == 2


def test_somar_com_corrida_soma_por_cima(monkeypatch):
    monkeypatch.setattr(metricas, "cache", CacheCorrida())

    metricas._somar("mensageria:metricas:corrida_ms", 2.5)

    assert metricas.cache.valores["mensageria:metricas:corrida_ms"] == 5000


@pytest.mark.parametrize(
    "operacao",
    [
        "publicacao",
        "consumo",
        "notificacao",
        "resumo",
    ],
)
def test_redis_indisponivel_degrada_para_log(monkeypatch, operacao):
    monkeypatch.setattr(metricas, "cache", RedisIndisponivel())

    if operacao == "publicacao":
        metricas.registrar_publicacao("sucesso", 10)
    elif operacao == "consumo":
        metricas.registrar_consumo(10, 5, duplicado=True, dlq=True)
    elif operacao == "notificacao":
        metricas.registrar_notificacao("aprovado")
    else:
        resumo = metricas.resumo()
        assert resumo["produtor"]["publicacoes"] == 0
        assert resumo["consumidor"]["consumos"] == 0
