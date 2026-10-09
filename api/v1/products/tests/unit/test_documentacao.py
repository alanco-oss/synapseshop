"""Testes das rotas de documentação e do envelope de erro (Aula 13)."""
from types import SimpleNamespace

from rest_framework.exceptions import NotFound, ValidationError

from products.exceptions import tratamento_de_erro


def test_schema_openapi_servido_pela_aplicacao(api_client):
    resposta = api_client.get("/api/v1/schema/")

    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "application/yaml"
    assert resposta.content.startswith(b"openapi: 3.0.3")


def test_swagger_ui_disponivel(api_client):
    resposta = api_client.get("/api/v1/docs/")

    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "text/html"
    assert b"swagger-ui" in resposta.content


def test_redoc_disponivel(api_client):
    resposta = api_client.get("/api/v1/redoc/")

    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "text/html"
    assert b"redoc" in resposta.content


def test_middleware_devolve_trace_id_gerado(api_client):
    resposta = api_client.get("/api/v1/schema/")

    assert resposta["X-Trace-Id"]


def test_middleware_preserva_trace_id_recebido(api_client):
    resposta = api_client.get("/api/v1/schema/", HTTP_X_TRACE_ID="trace-123")

    assert resposta["X-Trace-Id"] == "trace-123"


def test_erro_validacao_mantem_campos_no_topo():
    contexto = {"request": SimpleNamespace(path="/api/v1/pedidos/")}

    resposta = tratamento_de_erro(ValidationError({"total": ["negativo"]}), contexto)

    assert resposta.status_code == 400
    assert resposta.data["status"] == 400
    assert resposta.data["errors"] == {"total": ["negativo"]}
    assert resposta.data["total"] == ["negativo"]


def test_erro_detail_vira_detail_no_envelope():
    contexto = {"request": SimpleNamespace(path="/api/v1/pedidos/999/")}

    resposta = tratamento_de_erro(NotFound(), contexto)

    assert resposta.status_code == 404
    assert resposta.data["instance"] == "/api/v1/pedidos/999/"
    assert "detail" in resposta.data
