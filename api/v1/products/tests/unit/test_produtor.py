"""Testes unitários do produtor Kafka (orders/mensageria/produtor.py).

O ``AIOKafkaProducer`` real e substituído por um fake: o event loop de
background e a máquina de estado do módulo são exercitados por inteiro, mas
nenhum broker é contactado.
"""
import json

import pytest

from orders.mensageria import produtor, topicos


class FakeProducer:
    """Fake do ``AIOKafkaProducer`` com ligação e envio controláveis."""

    def __init__(self, bootstrap_servers=None, falhar_ligacao=False, falhar_envio=False):
        self.bootstrap_servers = bootstrap_servers
        self.falhar_ligacao = falhar_ligacao
        self.falhar_envio = falhar_envio
        self.arrancado = False
        self.parado = 0
        self.enviados = []

    async def start(self):
        if self.falhar_ligacao:
            raise RuntimeError("broker em baixo")
        self.arrancado = True

    async def stop(self):
        self.parado += 1
        self.arrancado = False

    async def send_and_wait(self, topico, value=None, key=None, headers=None):
        if self.falhar_envio:
            raise RuntimeError("envio recusado")
        self.enviados.append({"topico": topico, "value": value, "key": key})


EVENTO = {
    "event_type": "PedidoCriado",
    "idempotency_key": "pedido:1",
    "payload": {"pedido_id": 1},
}


@pytest.fixture(autouse=True)
def limpar_estado_produtor():
    """Garante que o estado global do módulo não vaza entre testes."""
    yield
    produtor.fechar()


def _instalar_fakes(monkeypatch, **kwargs):
    criados = []

    def fabrica(bootstrap_servers=None):
        instancia = FakeProducer(bootstrap_servers=bootstrap_servers, **kwargs)
        criados.append(instancia)
        return instancia

    monkeypatch.setattr(produtor, "AIOKafkaProducer", fabrica)
    return criados


def test_publicar_evento_com_sucesso(monkeypatch):
    criados = _instalar_fakes(monkeypatch)

    assert produtor.publicar_evento(EVENTO, topico=topicos.TOPICO_PEDIDO_CRIADO) is True

    produtor_fake = criados[0]
    assert produtor_fake.arrancado is True
    assert produtor_fake.bootstrap_servers == produtor.BOOTSTRAP_SERVERS

    envio = produtor_fake.enviados[0]
    assert envio["topico"] == topicos.TOPICO_PEDIDO_CRIADO
    assert json.loads(envio["value"]) == EVENTO
    assert envio["key"] == b"pedido:1"


def test_publicar_evento_com_falha_de_envio_devolve_false(monkeypatch):
    criados = _instalar_fakes(monkeypatch, falhar_envio=True)

    assert produtor.publicar_evento(EVENTO, topico=topicos.TOPICO_PEDIDO_CRIADO) is False
    assert criados[0].enviados == []


def test_publicar_evento_com_falha_de_ligacao_devolve_false(monkeypatch):
    _instalar_fakes(monkeypatch, falhar_ligacao=True)

    assert produtor.publicar_evento(EVENTO, topico=topicos.TOPICO_DLQ) is False


def test_estado_reinicia_apos_fechar(monkeypatch):
    criados = _instalar_fakes(monkeypatch)

    assert produtor.publicar_evento(EVENTO, topico=topicos.TOPICO_PEDIDO_CRIADO) is True
    produtor.fechar()
    assert produtor.publicar_evento(EVENTO, topico=topicos.TOPICO_PEDIDO_CRIADO) is True

    assert len(criados) == 2


def test_parar_produtor_que_levanta_erro(monkeypatch):
    class ProdutorAvaria(FakeProducer):
        async def stop(self):
            raise RuntimeError("stop em falha")

    criados = []

    def fabrica(bootstrap_servers=None):
        instancia = ProdutorAvaria(bootstrap_servers=bootstrap_servers)
        criados.append(instancia)
        return instancia

    monkeypatch.setattr(produtor, "AIOKafkaProducer", fabrica)

    assert produtor.publicar_evento(EVENTO, topico=topicos.TOPICO_PEDIDO_CRIADO) is True
    produtor.fechar()
