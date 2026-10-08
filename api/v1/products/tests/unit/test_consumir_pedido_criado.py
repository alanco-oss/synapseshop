"""Testes unitários do worker consumidor de ``PedidoCriado``.

O Kafka é totalmente substituído por fakes (consumidor, produtor DLQ) e o
``sync_to_async`` é reduzido a uma chamada direta para que o ORM corra na
própria thread do teste e veja a transação efémera (BD de teste do pytest-django).
"""
import asyncio
import json
from types import SimpleNamespace

import pytest

from orders.mensageria import idempotencia
from orders.management.commands import consumir_pedido_criado as cmd
from orders.models import Order


@pytest.fixture(autouse=True)
def sync_local(monkeypatch):
    """Faz ``sync_to_async`` executar na thread do teste (BD partilhada)."""

    def _falso(func, *args, **kwargs):
        async def _envolver(*argumentos, **kwargs_internos):
            return func(*argumentos, **kwargs_internos)

        return _envolver

    monkeypatch.setattr(cmd, "sync_to_async", _falso)


@pytest.fixture(autouse=True)
def sem_backoff(monkeypatch):
    """Backoff instantâneo: nenhum teste dorme à espera de reentregas."""
    monkeypatch.setattr(cmd, "BACKOFF_BASE", 0)
    monkeypatch.setattr(cmd, "BACKOFF_MAXIMO", 0)


def _rodar(corpo):
    """Corre ``corpo`` partilhando a ligação BD da transação do teste.

    ``asyncio.run`` cria a task com um contextvar storage próprio
    (asgiref ``Local`` em modo async) que não herda a ligação guardada no
    thread-local — sem esta cópia, o ORM abriria outra ligação cega à
    transação do pytest-django.
    """
    from django.db import connections

    conexao_principal = connections["default"]

    async def _com_conexao():
        from django.db import connections as ligacoes

        ligacoes["default"] = conexao_principal
        return await corpo

    return asyncio.run(_com_conexao())


def _evento(pedido_id, event_id="event-1"):
    return {
        "event_id": event_id,
        "event_type": "PedidoCriado",
        "occurred_at": "2026-01-15T11:59:59+00:00",
        "idempotency_key": f"pedido:{pedido_id}",
        "payload": {
            "pedido_id": pedido_id,
            "user_id": 7,
            "total": "129.90",
            "status": "pending",
            "created_at": "2026-01-15T11:59:59+00:00",
        },
    }


class Mensagem:
    def __init__(self, value, partition=0, offset=1, key=b"k"):
        self.value = value
        self.partition = partition
        self.offset = offset
        self.key = key


def _mensagem(evento):
    return Mensagem(json.dumps(evento).encode("utf-8"))


class FakeConsumidor:
    def __init__(self, falhar_start=False):
        self.falhar_start = falhar_start
        self.commits = 0
        self.parado = 0

    async def start(self):
        if self.falhar_start:
            raise RuntimeError("consumidor em baixo")

    async def stop(self):
        self.parado += 1

    async def commit(self):
        self.commits += 1


class FakeProdutorDLQ:
    def __init__(self, falhar=False):
        self.falhar = falhar
        self.enviados = []
        self.parado = 0

    async def start(self):
        pass

    async def stop(self):
        self.parado += 1

    async def send_and_wait(self, topico, value=None, key=None, headers=None):
        if self.falhar:
            raise RuntimeError("dlq em baixo")
        self.enviados.append({"topico": topico, "value": value, "key": key, "headers": dict(headers)})


# --- processar ---------------------------------------------------------------

@pytest.mark.django_db
def test_processar_novo_persiste_evento(cache_teste):
    pedido = Order.objects.create(user_id=7, total="129.90")

    desfecho = _rodar(cmd.processar(_mensagem(_evento(pedido.pk))))

    assert desfecho == "novo"
    pedido.refresh_from_db()
    assert pedido.evento_criado_em is not None
    assert idempotencia.tentar_reservar(f"pedido:{pedido.pk}", "outro") is False


@pytest.mark.django_db
def test_processar_duplicada_na_segunda_entrega(cache_teste):
    pedido = Order.objects.create(user_id=7, total="129.90")
    evento = _evento(pedido.pk)

    assert _rodar(cmd.processar(_mensagem(evento))) == "novo"
    assert _rodar(cmd.processar(_mensagem(evento))) == "duplicada"


@pytest.mark.django_db
def test_processar_reprocessa_reserva_sem_persistir(cache_teste):
    pedido = Order.objects.create(user_id=7, total="129.90")
    idempotencia.tentar_reservar(f"pedido:{pedido.pk}", "event-1")

    desfecho = _rodar(cmd.processar(_mensagem(_evento(pedido.pk))))

    assert desfecho == "novo"
    pedido.refresh_from_db()
    assert pedido.evento_criado_em is not None


def test_processar_mensagem_vazia():
    with pytest.raises(ValueError, match="mensagem_vazia"):
        _rodar(cmd.processar(Mensagem(b"")))


def test_processar_json_invalido():
    with pytest.raises(ValueError, match="json_invalido"):
        _rodar(cmd.processar(Mensagem(b"{nao e json")))


def test_processar_contrato_invalido():
    with pytest.raises(ValueError, match="campo obrigatorio em falta"):
        _rodar(cmd.processar(Mensagem(json.dumps({"event_type": "PedidoCriado"}).encode())))


def test_processar_forcar_falha(monkeypatch):
    monkeypatch.setattr(cmd, "FORCAR_FALHA", True)

    with pytest.raises(RuntimeError, match="falha_forcada"):
        _rodar(cmd.processar(Mensagem(b"{}")))


def test_latencia_ms_com_relogio_fixo(relogio_fixo):
    assert cmd._latencia_ms(_mensagem(_evento(1))) == 1000.0


def test_latencia_ms_payload_ilegivel():
    assert cmd._latencia_ms(Mensagem(b"nao-json")) == -1.0
    assert cmd._latencia_ms(Mensagem(b'{"occurred_at": "invalida"}')) == -1.0


def test_descrever_erro():
    assert cmd._descrever_erro(RuntimeError("boom")) == "RuntimeError: boom"
    assert cmd._descrever_erro(RuntimeError()) == "RuntimeError"


# --- _tratar -----------------------------------------------------------------

@pytest.mark.django_db
def test_tratar_sucesso_commit_e_metricas(cache_teste, relogio_fixo):
    pedido = Order.objects.create(user_id=7, total="129.90")
    consumidor = FakeConsumidor()
    dlq = FakeProdutorDLQ()

    _rodar(cmd.Command()._tratar(consumidor, dlq, _mensagem(_evento(pedido.pk))))

    assert consumidor.commits == 1
    assert dlq.enviados == []


@pytest.mark.django_db
def test_tratar_envia_para_dlq_esgotadas_tentativas(cache_teste, monkeypatch):
    monkeypatch.setattr(cmd, "N_TENTATIVAS", 2)
    monkeypatch.setattr(cmd, "FORCAR_FALHA", True)
    consumidor = FakeConsumidor()
    dlq = FakeProdutorDLQ()
    mensagem = Mensagem(b'{"event_type": "PedidoCriado"}', partition=2, offset=9, key=b"pedido:1")

    _rodar(cmd.Command()._tratar(consumidor, dlq, mensagem))

    assert consumidor.commits == 1
    assert len(dlq.enviados) == 1
    envio = dlq.enviados[0]
    assert envio["topico"] == "pedidos.criado.dlq"
    assert envio["value"] == mensagem.value
    assert envio["headers"]["x-tentativas"] == b"2"
    assert envio["headers"]["x-topico-original"] == b"pedidos.criado"
    assert envio["headers"]["x-particao"] == b"2"
    assert envio["headers"]["x-offset"] == b"9"
    assert b"falha_forcada" in envio["headers"]["x-error"]


@pytest.mark.django_db
def test_tratar_falha_na_dlq_propaga_sem_commit(cache_teste, monkeypatch):
    monkeypatch.setattr(cmd, "N_TENTATIVAS", 1)
    monkeypatch.setattr(cmd, "FORCAR_FALHA", True)
    consumidor = FakeConsumidor()
    dlq = FakeProdutorDLQ(falhar=True)

    with pytest.raises(RuntimeError, match="dlq em baixo"):
        _rodar(cmd.Command()._tratar(consumidor, dlq, Mensagem(b"{}")))

    assert consumidor.commits == 0


# --- _arrancar / _parar ------------------------------------------------------

def test_arrancar_repete_ate_conseguir(monkeypatch):
    atrasos = []

    async def dormir(atraso):
        atrasos.append(atraso)

    monkeypatch.setattr(cmd, "asyncio", SimpleNamespace(sleep=dormir, run=asyncio.run))

    tentativas = {"n": 0}

    def fabrica():
        tentativas["n"] += 1
        return FakeConsumidor(falhar_start=tentativas["n"] == 1)

    instancia = _rodar(cmd.Command()._arrancar(fabrica, "consumidor"))

    assert tentativas["n"] == 2
    assert atrasos == [1.0]


def test_parar_em_silencio_ignora_erros():
    class Avariado:
        async def stop(self):
            raise RuntimeError("stop em falha")

    _rodar(cmd.Command._parar_em_silencio(Avariado()))


# --- _consumir / handle ------------------------------------------------------

def test_consumir_processa_mensagens_e_para_tudo(monkeypatch):
    garantido = []
    tratados = []
    consumidores = []
    produtores = []

    class ConsumidorIteravel(FakeConsumidor):
        def __aiter__(self):
            self._it = iter([Mensagem(b"{}"), Mensagem(b"{}")])
            return self

        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    async def garantir_com_retry():
        garantido.append(1)

    def fabrica_consumidor(*args, **kwargs):
        instancia = ConsumidorIteravel()
        consumidores.append(instancia)
        return instancia

    def fabrica_produtor(*args, **kwargs):
        instancia = FakeProdutorDLQ()
        produtores.append(instancia)
        return instancia

    async def tratar(self, consumidor, produtor_dlq, mensagem):
        tratados.append(mensagem)

    monkeypatch.setattr(cmd.topicos, "garantir_com_retry", garantir_com_retry)
    monkeypatch.setattr(cmd, "AIOKafkaConsumer", fabrica_consumidor)
    monkeypatch.setattr(cmd, "AIOKafkaProducer", fabrica_produtor)
    monkeypatch.setattr(cmd.Command, "_tratar", tratar)

    _rodar(cmd.Command()._consumir())

    assert garantido == [1]
    assert len(tratados) == 2
    assert consumidores[0].parado == 1
    assert produtores[0].parado == 1


def test_handle_delega_no_consumir(monkeypatch):
    chamado = []

    async def consumir(self):
        chamado.append(1)

    monkeypatch.setattr(cmd.Command, "_consumir", consumir)

    cmd.Command().handle()

    assert chamado == [1]
