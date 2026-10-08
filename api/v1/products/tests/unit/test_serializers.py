"""Testes unitários dos serializers (orders e catalog)."""
from decimal import Decimal

import pytest
from rest_framework.serializers import ValidationError

from catalog.serializers import ItemSerializer
from orders.serializers import OrderSerializer, PagamentoSimuladoSerializer


@pytest.mark.parametrize(
    "total,valido",
    [
        ("0.00", True),
        ("129.90", True),
        ("9999999.99", True),
        ("-0.01", False),
        ("-10.00", False),
    ],
)
def test_order_serializer_validate_total(total, valido):
    serializer = OrderSerializer(
        data={"user_id": 7, "status": "pending", "total": total}
    )

    assert serializer.is_valid() is valido
    if not valido:
        assert "total" in serializer.errors
        assert "não negativo" in str(serializer.errors["total"])


def test_order_serializer_valido_normaliza_o_total():
    serializer = OrderSerializer(
        data={"user_id": 7, "status": "pending", "total": "42.50"}
    )

    assert serializer.is_valid() is True
    assert serializer.validated_data["total"] == Decimal("42.50")


@pytest.mark.parametrize(
    "payload,valido",
    [
        ({}, True),
        ({"aprovado": True}, True),
        ({"aprovado": False}, True),
        ({"aprovado": 1}, True),
        ({"aprovado": "sim"}, False),
        ({"aprovado": "talvez"}, False),
    ],
)
def test_pagamento_serializer_validacao_de_booleano(payload, valido):
    serializer = PagamentoSimuladoSerializer(data=payload)

    assert serializer.is_valid() is valido
    if not valido:
        assert "aprovado" in serializer.errors


def test_pagamento_serializer_default_e_aprovado_true():
    serializer = PagamentoSimuladoSerializer(data={})

    assert serializer.is_valid() is True
    assert serializer.validated_data["aprovado"] is True


@pytest.mark.parametrize("campo_desconhecido", ["valor", "moeda", "idempotency_key"])
def test_pagamento_serializer_rejeita_campos_desconhecidos(campo_desconhecido):
    serializer = PagamentoSimuladoSerializer(
        data={"aprovado": True, campo_desconhecido: "x"}
    )

    assert serializer.is_valid() is False
    assert campo_desconhecido in serializer.errors


@pytest.mark.parametrize(
    "preco,valido",
    [
        (Decimal("0.00"), True),
        (Decimal("9.99"), True),
        (Decimal("-0.01"), False),
        (Decimal("-100"), False),
    ],
)
def test_item_serializer_validate_preco(preco, valido):
    serializer = ItemSerializer()

    if valido:
        assert serializer.validate_preco(preco) == preco
    else:
        with pytest.raises(ValidationError, match="não negativo"):
            serializer.validate_preco(preco)
