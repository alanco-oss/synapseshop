"""Testes de integração do ciclo de vida de um pedido na API.

Validam o contrato HTTP (status codes), a persistência na base de dados e a
publicação do evento ``PedidoCriado`` com o produtor Kafka substituído por um
fake (fixture ``publicador_falso``).
"""
import pytest

from orders import cache as cache_pedidos
from orders.mensageria import contrato, topicos
from orders.models import Order

pytestmark = pytest.mark.django_db


def test_ciclo_vida_completo_post_get(api_client, fabrica_pedido, publicador_falso):
    criado = api_client.post("/api/v1/pedidos/", fabrica_pedido(), format="json")

    assert criado.status_code == 201
    pedido_id = criado.json()["id"]
    assert criado.json()["status"] == "pending"

    assert Order.objects.filter(pk=pedido_id, user_id=7, status="pending").exists()

    assert len(publicador_falso) == 1
    assert publicador_falso[0]["topico"] == topicos.TOPICO_PEDIDO_CRIADO
    contrato.validar(publicador_falso[0]["evento"])
    assert publicador_falso[0]["evento"]["idempotency_key"] == f"pedido:{pedido_id}"

    detalhe = api_client.get(f"/api/v1/pedidos/{pedido_id}/")

    assert detalhe.status_code == 200
    assert detalhe.json()["id"] == pedido_id
    assert detalhe.json()["total"] == "129.90"


def test_lista_reflete_criacao_e_metricas_de_cache(api_client, fabrica_pedido, publicador_falso):
    antes = api_client.get("/api/v1/pedidos/")
    assert antes.status_code == 200

    criado = api_client.post("/api/v1/pedidos/", fabrica_pedido(), format="json")
    assert criado.status_code == 201

    depois = api_client.get("/api/v1/pedidos/")
    assert depois.status_code == 200
    assert any(item["id"] == criado.json()["id"] for item in depois.json())

    repetido = api_client.get("/api/v1/pedidos/")
    assert repetido.json() == depois.json()

    metricas = api_client.get("/api/v1/pedidos/metricas-cache/")
    assert metricas.status_code == 200
    lista = metricas.json()["lista"]
    assert lista["lookups"] >= 3
    assert lista["hits"] >= 1
    assert lista["misses"] >= 2


def test_criacao_com_total_negativo_devolve_400(api_client, fabrica_pedido, publicador_falso):
    resposta = api_client.post(
        "/api/v1/pedidos/", fabrica_pedido(total="-10.00"), format="json"
    )

    assert resposta.status_code == 400
    assert "total" in resposta.json()
    assert Order.objects.count() == 0
    assert publicador_falso == []


def test_detalhes_invalidez_cache_apos_atualizacao(api_client, fabrica_pedido, publicador_falso):
    criado = api_client.post("/api/v1/pedidos/", fabrica_pedido(), format="json")
    pedido_id = criado.json()["id"]

    detalhe = api_client.get(f"/api/v1/pedidos/{pedido_id}/detalhes/")

    assert detalhe.status_code == 200
    assert detalhe.json()["id"] == pedido_id
    assert cache_pedidos.cache.get(cache_pedidos.chave_detalhes(pedido_id)) is not None

    atualizado = api_client.patch(
        f"/api/v1/pedidos/{pedido_id}/", {"status": "cancelled"}, format="json"
    )

    assert atualizado.status_code == 200
    assert cache_pedidos.cache.get(cache_pedidos.chave_detalhes(pedido_id)) is None
    assert Order.objects.get(pk=pedido_id).status == "cancelled"


def test_metricas_mensageria_disponiveis(api_client, fabrica_pedido, publicador_falso):
    api_client.post("/api/v1/pedidos/", fabrica_pedido(), format="json")

    resposta = api_client.get("/api/v1/pedidos/metricas-mensageria/")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["produtor"]["publicacoes"] == 0
    assert corpo["consumidor"]["consumos"] == 0
    assert corpo["notificacoes"] == {"total": 0, "aprovados": 0, "recusados": 0}


def test_remocao_de_pedido_apaga_da_base_de_dados(api_client, fabrica_pedido, publicador_falso):
    criado = api_client.post("/api/v1/pedidos/", fabrica_pedido(), format="json")
    pedido_id = criado.json()["id"]

    removido = api_client.delete(f"/api/v1/pedidos/{pedido_id}/")

    assert removido.status_code == 204
    assert not Order.objects.filter(pk=pedido_id).exists()
    assert api_client.get(f"/api/v1/pedidos/{pedido_id}/").status_code == 404
