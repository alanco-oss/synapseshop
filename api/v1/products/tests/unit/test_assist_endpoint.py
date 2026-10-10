"""Testes do endpoint ``POST /api/v1/assist`` (Aula 14)."""
import requests

from assist.circuit_breaker import Interruptor

PAYLOAD_VALIDO = {
    "mode": "summarize",
    "logs": ["autenticacao de joao@empresa.com", "timeout no pagamento"],
    "temperature": 0.3,
    "max_tokens": 256,
}


class FakeResposta:
    def __init__(self, status_code, corpo):
        self.status_code = status_code
        self._corpo = corpo
        self.url = "https://provedor-de-teste.local/v1/chat/completions"
        self.duracao_ms = 1.5

    def json(self):
        return self._corpo


def resposta_ok(answer="resumo gerado", tokens_prompt=15, tokens_output=40):
    return FakeResposta(
        200,
        {
            "choices": [{"message": {"content": answer}}],
            "usage": {"prompt_tokens": tokens_prompt,
                      "completion_tokens": tokens_output},
        },
    )


def _post(api_client, payload):
    return api_client.post("/api/v1/assist", payload, format="json")


def test_assist_responde_200_com_answer_e_meta(
    api_client, provedor_falso, sem_dormir
):
    provedor_falso["fila"].append(resposta_ok("resumo", 15, 40))
    resposta = _post(api_client, PAYLOAD_VALIDO)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo == {
        "answer": "resumo",
        "meta": {"tokens_prompt": 15, "tokens_output": 40},
    }


def test_assist_envia_logs_redigidos_ao_provedor(
    api_client, provedor_falso, sem_dormir
):
    provedor_falso["fila"].append(resposta_ok("resumo", 15, 40))
    _post(api_client, PAYLOAD_VALIDO)
    mensagens = provedor_falso["registo"]["payloads"][0]["messages"]
    conteudo_utilizador = mensagens[1]["content"]
    assert "joao@empresa.com" not in conteudo_utilizador
    assert "[REDIGIDO:email]" in conteudo_utilizador


def test_assist_aceita_logs_como_string(api_client, provedor_falso, sem_dormir):
    provedor_falso["fila"].append(resposta_ok("resumo", 3, 7))
    resposta = _post(
        api_client,
        {"mode": "summarize", "logs": "linha unica de log"},
    )
    assert resposta.status_code == 200
    assert resposta.json()["answer"] == "resumo"


def test_assist_aplica_defaults_quando_omitidos(
    api_client, provedor_falso, sem_dormir
):
    provedor_falso["fila"].append(resposta_ok("resumo", 3, 7))
    _post(api_client, {"mode": "explain", "logs": "log"})
    payload = provedor_falso["registo"]["payloads"][0]
    assert payload["temperature"] == 0.3
    assert payload["max_tokens"] == 256


def test_assist_mode_invalido_devolve_400(api_client):
    resposta = _post(api_client, {"mode": "traduzir", "logs": "log"})
    assert resposta.status_code == 400


def test_assist_temperature_fora_de_0_1_devolve_400(api_client):
    for valor in (-0.1, 1.5):
        resposta = _post(
            api_client, {"mode": "summarize", "logs": "log", "temperature": valor}
        )
        assert resposta.status_code == 400


def test_assist_max_tokens_invalido_devolve_400(api_client):
    for valor in (0, -5):
        resposta = _post(
            api_client, {"mode": "summarize", "logs": "log", "max_tokens": valor}
        )
        assert resposta.status_code == 400


def test_assist_logs_com_tipo_invalido_devolve_400(api_client):
    for valor in ({"log": "x"}, ["log", 42]):
        resposta = _post(
            api_client, {"mode": "summarize", "logs": valor}
        )
        assert resposta.status_code == 400


def test_assist_campo_desconhecido_devolve_400(api_client):
    payload = {**PAYLOAD_VALIDO, "modelo": "gpt-x"}
    resposta = _post(api_client, payload)
    assert resposta.status_code == 400


def test_assist_corpo_incompleto_devolve_400(api_client):
    for payload in ({}, {"logs": "sem modo"}):
        resposta = _post(api_client, payload)
        assert resposta.status_code == 400


def test_assist_provedor_queda_total_devolve_503(
    api_client, provedor_falso, sem_dormir
):
    provedor_falso["fila"].extend(
        [requests.Timeout("timeout") for _ in range(3)]
    )
    resposta = _post(api_client, PAYLOAD_VALIDO)
    assert resposta.status_code == 503
    envelope = resposta.json()
    assert envelope["title"] == "Serviço indisponível"
    assert envelope["status"] == 503


def test_assist_erro_4xx_do_provedor_devolve_502(
    api_client, provedor_falso, sem_dormir
):
    provedor_falso["fila"].append(FakeResposta(401, {}))
    resposta = _post(api_client, PAYLOAD_VALIDO)
    assert resposta.status_code == 502
    envelope = resposta.json()
    assert envelope["title"] == "Gateway inválido"
    assert envelope["status"] == 502


def test_assist_circuito_aberto_devolve_503_sem_provedor(
    api_client, provedor_falso, sem_dormir, monkeypatch
):
    interruptor = Interruptor(falhas_para_abrir=1, timeout_aberto=1000)
    monkeypatch.setattr("assist.llm_service.INTERRUPTOR", interruptor)

    provedor_falso["fila"].extend([FakeResposta(500, {})] * 3)
    assert _post(api_client, PAYLOAD_VALIDO).status_code == 503
    # Provedor (mock) nao recebe mais chamadas enquanto o circuito estiver aberto.
    resultado = _post(api_client, PAYLOAD_VALIDO)
    assert resultado.status_code == 503
    assert provedor_falso["registo"]["chamadas"] == 3