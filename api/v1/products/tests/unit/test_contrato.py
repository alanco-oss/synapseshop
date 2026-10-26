"""Testes unitários dos contratos de eventos (orders/mensageria/contrato.py)."""
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest

from orders.mensageria import contrato


@pytest.fixture
def pedido():
    """Pedido em memória: o contrato só lê atributos, não toca na BD."""
    return SimpleNamespace(
        pk=42,
        user_id=7,
        total=Decimal("129.90"),
        status="pending",
        created_at=datetime(2026, 1, 15, 11, 59, 59, tzinfo=UTC),
    )


def test_chave_idempotencia_e_de_negocio():
    assert contrato.chave_idempotencia(42) == "pedido:42"
    assert contrato.chave_idempotencia_pagamento(42) == "pagamento:42"


def test_construir_pedido_criado_respeita_contrato(pedido, relogio_fixo):
    evento = contrato.construir_pedido_criado(pedido)

    assert evento["event_type"] == "PedidoCriado"
    assert evento["occurred_at"] == "2026-01-15T12:00:00+00:00"
    assert evento["idempotency_key"] == "pedido:42"
    UUID(evento["event_id"])
    assert evento["payload"] == {
        "pedido_id": 42,
        "user_id": 7,
        "total": "129.90",
        "status": "pending",
        "created_at": "2026-01-15T11:59:59+00:00",
    }
    assert contrato.validar(evento) is evento


@pytest.mark.parametrize("aprovado", [True, False])
def test_construir_pagamento_simulado_respeita_contrato(pedido, aprovado):
    evento = contrato.construir_pagamento_simulado(pedido, aprovado)

    assert evento["event_type"] == "PagamentoSimulado"
    assert evento["idempotency_key"] == "pagamento:42"
    assert evento["payload"]["aprovado"] is aprovado
    assert evento["payload"]["status"] == "pending"
    assert contrato.validar_pagamento(evento) is evento


def test_validar_rejeita_nao_dict():
    with pytest.raises(ValueError, match="nao e um objeto JSON"):
        contrato.validar("nao-e-evento")


def test_validar_rejeita_payload_nao_dict(pedido):
    evento = contrato.construir_pedido_criado(pedido)
    evento["payload"] = "corpo-simples"

    with pytest.raises(ValueError, match="payload nao e um objeto JSON"):
        contrato.validar(evento)


@pytest.mark.parametrize("campo", list(contrato.CAMPOS_OBRIGATORIOS))
def test_validar_rejeita_campo_de_topo_em_falta(pedido, campo):
    evento = contrato.construir_pedido_criado(pedido)
    del evento[campo]

    with pytest.raises(ValueError, match=f"campo obrigatorio em falta: {campo}"):
        contrato.validar(evento)


@pytest.mark.parametrize("campo", list(contrato.PAYLOAD_OBRIGATORIO))
def test_validar_rejeita_campo_do_payload_em_falta(pedido, campo):
    evento = contrato.construir_pedido_criado(pedido)
    del evento["payload"][campo]

    with pytest.raises(ValueError, match=f"payload.{campo}"):
        contrato.validar(evento)


def test_validar_rejeita_event_type_desconhecido(pedido):
    evento = contrato.construir_pedido_criado(pedido)
    evento["event_type"] = "PedidoApagado"

    with pytest.raises(ValueError, match="event_type desconhecido"):
        contrato.validar(evento)


def test_validar_pagamento_rejeita_nao_dict():
    with pytest.raises(ValueError, match="nao e um objeto JSON"):
        contrato.validar_pagamento([1, 2, 3])


def test_validar_pagamento_rejeita_payload_nao_dict(pedido):
    evento = contrato.construir_pagamento_simulado(pedido, True)
    evento["payload"] = "corpo-simples"

    with pytest.raises(ValueError, match="payload nao e um objeto JSON"):
        contrato.validar_pagamento(evento)


@pytest.mark.parametrize("campo", list(contrato.CAMPOS_OBRIGATORIOS))
def test_validar_pagamento_rejeita_campo_de_topo_em_falta(pedido, campo):
    evento = contrato.construir_pagamento_simulado(pedido, True)
    del evento[campo]

    with pytest.raises(ValueError, match=f"campo obrigatorio em falta: {campo}"):
        contrato.validar_pagamento(evento)


def test_validar_pagamento_rejeita_event_type_desconhecido(pedido):
    evento = contrato.construir_pagamento_simulado(pedido, True)
    evento["event_type"] = "PedidoCriado"

    with pytest.raises(ValueError, match="event_type desconhecido"):
        contrato.validar_pagamento(evento)


@pytest.mark.parametrize("campo", list(contrato.PAYLOAD_PAGAMENTO_OBRIGATORIO))
def test_validar_pagamento_rejeita_campo_do_payload_em_falta(pedido, campo):
    evento = contrato.construir_pagamento_simulado(pedido, True)
    del evento["payload"][campo]

    with pytest.raises(ValueError, match=f"payload.{campo}"):
        contrato.validar_pagamento(evento)


def test_validar_pagamento_rejeita_aprovado_nao_booleano(pedido):
    evento = contrato.construir_pagamento_simulado(pedido, True)
    evento["payload"]["aprovado"] = "sim"

    with pytest.raises(ValueError, match="payload.aprovado tem de ser booleano"):
        contrato.validar_pagamento(evento)
