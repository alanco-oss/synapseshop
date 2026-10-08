"""Testes unitários da garantia de tópicos Kafka (orders/mensageria/topicos.py)."""
import asyncio as asyncio_real
from types import SimpleNamespace

import pytest
from aiokafka.admin import NewPartitions, NewTopic

from orders.mensageria import topicos


class FakeAdmin:
    """Fake do ``AIOKafkaAdminClient`` com estado inspecionável."""

    def __init__(self, bootstrap_servers=None, existentes=(), particoes=None, falhar_start=False):
        self.bootstrap_servers = bootstrap_servers
        self.existentes = set(existentes)
        self.particoes = particoes or {}
        self.falhar_start = falhar_start
        self.criados = []
        self.aumentados = {}
        self.fechado = 0

    async def start(self):
        if self.falhar_start:
            raise RuntimeError("kafka em baixo")

    async def close(self):
        self.fechado += 1

    async def list_topics(self):
        return set(self.existentes)

    async def describe_topics(self, nomes):
        return [
            {"topic": nome, "partitions": [i for i in range(self.particoes.get(nome, 1))]}
            for nome in nomes
        ]

    async def create_topics(self, temaspos):
        self.criados.extend(temaspos)

    async def create_partitions(self, mapa):
        self.aumentados.update({k: v.total_count for k, v in mapa.items()})


def _instalar(monkeypatch, **kwargs):
    criados = []

    def fabrica(bootstrap_servers=None):
        instancia = FakeAdmin(bootstrap_servers=bootstrap_servers, **kwargs)
        criados.append(instancia)
        return instancia

    monkeypatch.setattr(topicos, "AIOKafkaAdminClient", fabrica)
    return criados


def test_garantir_cria_todos_os_topicos_em_falta(monkeypatch):
    criados = _instalar(monkeypatch, existentes=())

    asyncio_real.run(topicos.garantir())

    admin = criados[0]
    assert len(admin.criados) == len(topicos.ESPECIFICACOES)
    nomes = {topico.name for topico in admin.criados}
    assert nomes == set(topicos.ESPECIFICACOES)

    detalhe = {t.name: t for t in admin.criados}[topicos.TOPICO_PEDIDO_CRIADO]
    assert isinstance(detalhe, NewTopic)
    assert detalhe.num_partitions == topicos.PARTICOES
    assert detalhe.topic_configs["retention.ms"] == str(topicos.RETENCAO_HORAS * 3600 * 1000)
    assert admin.fechado == 1


def test_garantir_valida_topicos_ja_configurados(monkeypatch):
    existentes = list(topicos.ESPECIFICACOES)
    particoes = {
        topicos.TOPICO_PEDIDO_CRIADO: topicos.PARTICOES,
        topicos.TOPICO_DLQ: 1,
        topicos.TOPICO_PAGAMENTO: topicos.PARTICOES,
        topicos.TOPICO_PAGAMENTO_DLQ: 1,
    }
    criados = _instalar(monkeypatch, existentes=existentes, particoes=particoes)

    asyncio_real.run(topicos.garantir())

    admin = criados[0]
    assert admin.criados == []
    assert admin.aumentados == {}


def test_garantir_aumenta_particoes_em_falta(monkeypatch):
    existentes = list(topicos.ESPECIFICACOES)
    particoes = {
        topicos.TOPICO_PEDIDO_CRIADO: 1,
        topicos.TOPICO_DLQ: 1,
        topicos.TOPICO_PAGAMENTO: 1,
        topicos.TOPICO_PAGAMENTO_DLQ: 1,
    }
    criados = _instalar(monkeypatch, existentes=existentes, particoes=particoes)

    asyncio_real.run(topicos.garantir())

    admin = criados[0]
    assert admin.criados == []
    assert admin.aumentados[topicos.TOPICO_PEDIDO_CRIADO] == topicos.PARTICOES
    assert admin.aumentados[topicos.TOPICO_PAGAMENTO] == topicos.PARTICOES
    assert topicos.TOPICO_DLQ not in admin.aumentados


def test_garantir_descreve_topicos_como_objeto(monkeypatch):
    """Cobre o ramo em que ``describe_topics`` devolve objetos (aiokafka novo)."""
    existentes = [topicos.TOPICO_PEDIDO_CRIADO]

    class FakeAdminObjeto(FakeAdmin):
        async def describe_topics(self, nomes):
            return [
                SimpleNamespace(topic=nome, partitions=[0])
                for nome in nomes
            ]

    def fabrica(bootstrap_servers=None):
        return FakeAdminObjeto(
            bootstrap_servers=bootstrap_servers,
            existentes=existentes,
            particoes={topicos.TOPICO_PEDIDO_CRIADO: 1},
        )

    monkeypatch.setattr(topicos, "AIOKafkaAdminClient", fabrica)

    asyncio_real.run(topicos.garantir())


def test_garantir_propaga_erro_de_ligacao(monkeypatch):
    criados = _instalar(monkeypatch, falhar_start=True)

    with pytest.raises(RuntimeError, match="kafka em baixo"):
        asyncio_real.run(topicos.garantir())

    assert criados[0].fechado == 1


def test_garantir_ignora_erro_no_fecho(monkeypatch):
    class FakeAdminFechaAvaria(FakeAdmin):
        async def close(self):
            self.fechado += 1
            raise RuntimeError("close em falha")

    def fabrica(bootstrap_servers=None):
        return FakeAdminFechaAvaria(bootstrap_servers=bootstrap_servers)

    monkeypatch.setattr(topicos, "AIOKafkaAdminClient", fabrica)

    asyncio_real.run(topicos.garantir())


def test_particoes_aceita_dict_e_objeto():
    assert len(topicos._particoes({"partitions": [0, 1]})) == 2
    assert len(topicos._particoes(SimpleNamespace(partitions=[0]))) == 1


def test_garantir_com_retry_repete_ate_conseguir(monkeypatch):
    tentativas = []
    atrasos = []
    chamadas = {"n": 0}

    async def garantir_instavel():
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise RuntimeError("arranque imperfeito")

    async def dormir(atraso):
        atrasos.append(atraso)

    monkeypatch.setattr(topicos, "garantir", garantir_instavel)
    monkeypatch.setattr(topicos, "asyncio", SimpleNamespace(sleep=dormir))

    asyncio_real.run(topicos.garantir_com_retry())

    assert chamadas["n"] == 2
    assert atrasos == [1.0]


def test_garantir_sync_delega_no_retry(monkeypatch):
    chamado = []

    async def garantir_com_retry():
        chamado.append(1)

    monkeypatch.setattr(topicos, "garantir_com_retry", garantir_com_retry)

    topicos.garantir_sync()

    assert chamado == [1]


def test_especificacoes_usam_constantes_ambiente():
    for nome, cfg in topicos.ESPECIFICACOES.items():
        assert cfg["particoes"] >= 1
        assert cfg["retencao_ms"] > 0
        assert isinstance(nome, str)

    assert topicos.ESPECIFICACOES[topicos.TOPICO_DLQ]["particoes"] == 1
