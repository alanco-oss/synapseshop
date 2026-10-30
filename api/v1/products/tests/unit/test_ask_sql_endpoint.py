"""Testes do endpoint ``POST /api/v1/ask_sql`` (Aula 21)."""

import json

import pytest
import requests

from assist.circuit_breaker import Interruptor
from orders.models import Order

pytestmark = pytest.mark.django_db

PAYLOAD_VALIDO = {"question": "Quais os 5 ultimos pedidos?"}
SQL_VALIDA = (
    "SELECT id, status, total FROM orders_order ORDER BY id LIMIT 5"
)


class FakeResposta:
    def __init__(self, status_code, corpo):
        self.status_code = status_code
        self._corpo = corpo
        self.url = "https://provedor-de-teste.local/v1/chat/completions"
        self.duracao_ms = 1.5

    def json(self):
        return self._corpo


def resposta_ok(sql=SQL_VALIDA, params=None, tokens_prompt=10, tokens_output=20):
    conteudo = json.dumps({"sql": sql, "params": params or []})
    return FakeResposta(
        200,
        {
            "choices": [{"message": {"content": conteudo}}],
            "usage": {
                "prompt_tokens": tokens_prompt,
                "completion_tokens": tokens_output,
            },
        },
    )


def _post(api_client, payload=None):
    dados = PAYLOAD_VALIDO if payload is None else payload
    return api_client.post("/api/v1/ask_sql", dados, format="json")


def test_ask_sql_200_devolve_sql_e_resultados(api_client, provedor_falso, sem_dormir):
    Order.objects.create(user_id=1, total="10.00")
    provedor_falso["fila"].append(resposta_ok())

    resposta = _post(api_client)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["sql"].startswith("SELECT")
    assert corpo["columns"] == ["id", "status", "total"]
    assert corpo["row_count"] == 1
    assert corpo["results"][0]["total"] == 10.0
    assert corpo["meta"]["tokens_prompt"] == 10
    assert corpo["meta"]["tokens_output"] == 20


def test_ask_sql_envia_schema_e_pergunta_redigida(
    api_client, provedor_falso, sem_dormir
):
    provedor_falso["fila"].append(resposta_ok())
    _post(api_client, {"question": "pedidos de joao@empresa.com"})

    mensagens = provedor_falso["registo"]["payloads"][0]["messages"]
    assert "orders_order" in mensagens[0]["content"]
    assert "joao@empresa.com" not in mensagens[1]["content"]
    assert "[REDIGIDO:email]" in mensagens[1]["content"]


def test_ask_sql_aplica_defaults(api_client, provedor_falso, sem_dormir):
    provedor_falso["fila"].append(resposta_ok())
    _post(api_client)

    payload = provedor_falso["registo"]["payloads"][0]
    assert payload["temperature"] == 0.0
    assert payload["max_tokens"] == 512


def test_ask_sql_payload_invalido_devolve_400(api_client):
    for payload in ({}, {"question": ""}, {"question": "x", "modelo": "gpt"}):
        assert _post(api_client, payload).status_code == 400


def test_ask_sql_injeta_limit_quando_ausente(api_client, provedor_falso, sem_dormir):
    Order.objects.create(user_id=1, total="5.00")
    provedor_falso["fila"].append(
        resposta_ok(sql="SELECT id FROM orders_order ORDER BY id")
    )

    resposta = _post(api_client)

    assert resposta.status_code == 200
    assert "LIMIT 100" in resposta.json()["sql"]


def test_ask_sql_comando_de_escrita_devolve_422(
    api_client, provedor_falso, sem_dormir
):
    provedor_falso["fila"].append(resposta_ok(sql="DELETE FROM orders_order"))

    resposta = _post(api_client)

    assert resposta.status_code == 422
    assert resposta.json()["title"] == "Entidade não processável"


def test_ask_sql_tabela_fora_da_allow_list_devolve_422(
    api_client, provedor_falso, sem_dormir
):
    provedor_falso["fila"].append(resposta_ok(sql="SELECT id FROM users"))

    resposta = _post(api_client)

    assert resposta.status_code == 422


def test_ask_sql_falha_de_execucao_devolve_422(
    api_client, provedor_falso, sem_dormir
):
    provedor_falso["fila"].append(
        resposta_ok(sql="SELECT coluna_inexistente FROM orders_order")
    )

    resposta = _post(api_client)

    assert resposta.status_code == 422


def test_ask_sql_erro_4xx_do_provedor_devolve_502(
    api_client, provedor_falso, sem_dormir
):
    provedor_falso["fila"].append(FakeResposta(401, {}))

    resposta = _post(api_client)

    assert resposta.status_code == 502
    assert resposta.json()["title"] == "Gateway inválido"


def test_ask_sql_provedor_indisponivel_devolve_503(
    api_client, provedor_falso, sem_dormir
):
    provedor_falso["fila"].extend([requests.Timeout("timeout") for _ in range(3)])

    resposta = _post(api_client)

    assert resposta.status_code == 503
    assert resposta.json()["title"] == "Serviço indisponível"


def test_ask_sql_circuito_aberto_devolve_503_sem_provedor(
    api_client, provedor_falso, sem_dormir, monkeypatch
):
    interruptor = Interruptor(falhas_para_abrir=1, timeout_aberto=1000)
    monkeypatch.setattr("assist.llm_service.INTERRUPTOR", interruptor)

    provedor_falso["fila"].extend([FakeResposta(500, {})] * 3)
    assert _post(api_client).status_code == 503

    resultado = _post(api_client)
    assert resultado.status_code == 503
    assert provedor_falso["registo"]["chamadas"] == 3
