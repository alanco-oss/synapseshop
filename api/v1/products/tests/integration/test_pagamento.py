"""Testes de integração do fluxo de pagamento simulado (Aula 11)."""
import pytest

from orders import cache as cache_pedidos
from orders.mensageria import contrato, topicos
from orders.models import Order

pytestmark = pytest.mark.django_db


def _criar_pedido(api_client, fabrica_pedido, publicador_falso):
    resposta = api_client.post("/api/v1/pedidos/", fabrica_pedido(), format="json")
    assert resposta.status_code == 201
    return resposta.json()["id"]


def test_pagar_aprovado_transiciona_para_paid(api_client, fabrica_pedido, publicador_falso):
    pedido_id = _criar_pedido(api_client, fabrica_pedido, publicador_falso)
    publicador_falso.clear()

    resposta = api_client.post(
        f"/api/v1/pedidos/{pedido_id}/pagar/", {"aprovado": True}, format="json"
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "paid"
    assert corpo["aprovado"] is True
    assert corpo["evento_publicado"] is True

    pedido = Order.objects.get(pk=pedido_id)
    assert pedido.status == "paid"

    assert len(publicador_falso) == 1
    assert publicador_falso[0]["topico"] == topicos.TOPICO_PAGAMENTO
    evento = publicador_falso[0]["evento"]
    contrato.validar_pagamento(evento)
    assert evento["idempotency_key"] == f"pagamento:{pedido_id}"
    assert evento["payload"]["aprovado"] is True


def test_pagar_recusado_devolve_402_e_mantem_pending(api_client, fabrica_pedido, publicador_falso):
    pedido_id = _criar_pedido(api_client, fabrica_pedido, publicador_falso)
    publicador_falso.clear()

    resposta = api_client.post(
        f"/api/v1/pedidos/{pedido_id}/pagar/", {"aprovado": False}, format="json"
    )

    assert resposta.status_code == 402
    assert resposta.json()["aprovado"] is False
    assert Order.objects.get(pk=pedido_id).status == "pending"

    assert len(publicador_falso) == 1
    evento = publicador_falso[0]["evento"]
    contrato.validar_pagamento(evento)
    assert evento["payload"]["aprovado"] is False


def test_pagar_sem_payload_aprova_por_omissao(api_client, fabrica_pedido, publicador_falso):
    pedido_id = _criar_pedido(api_client, fabrica_pedido, publicador_falso)

    resposta = api_client.post(f"/api/v1/pedidos/{pedido_id}/pagar/", {}, format="json")

    assert resposta.status_code == 200
    assert Order.objects.get(pk=pedido_id).status == "paid"


def test_pagar_pagamento_repetido_devolve_409(api_client, fabrica_pedido, publicador_falso):
    pedido_id = _criar_pedido(api_client, fabrica_pedido, publicador_falso)
    api_client.post(
        f"/api/v1/pedidos/{pedido_id}/pagar/", {"aprovado": True}, format="json"
    )
    publicador_falso.clear()

    repetido = api_client.post(
        f"/api/v1/pedidos/{pedido_id}/pagar/", {"aprovado": True}, format="json"
    )

    assert repetido.status_code == 409
    assert "nao esta pendente" in repetido.json()["detail"]
    assert publicador_falso == []


@pytest.mark.parametrize(
    "payload",
    [
        {"aprovado": "sim"},
        {"aprovado": True, "moeda": "EUR"},
        {"valor": 100},
    ],
)
def test_pagar_payload_invalido_devolve_400(api_client, fabrica_pedido, publicador_falso, payload):
    pedido_id = _criar_pedido(api_client, fabrica_pedido, publicador_falso)
    publicador_falso.clear()

    resposta = api_client.post(
        f"/api/v1/pedidos/{pedido_id}/pagar/", payload, format="json"
    )

    assert resposta.status_code == 400
    assert Order.objects.get(pk=pedido_id).status == "pending"
    assert publicador_falso == []


def test_pagar_invalidez_cache_do_detalhe(api_client, fabrica_pedido, publicador_falso):
    pedido_id = _criar_pedido(api_client, fabrica_pedido, publicador_falso)
    api_client.get(f"/api/v1/pedidos/{pedido_id}/detalhes/")
    assert cache_pedidos.cache.get(cache_pedidos.chave_detalhes(pedido_id)) is not None

    api_client.post(
        f"/api/v1/pedidos/{pedido_id}/pagar/", {"aprovado": True}, format="json"
    )

    assert cache_pedidos.cache.get(cache_pedidos.chave_detalhes(pedido_id)) is None
