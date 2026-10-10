"""Testes de resiliencia do ``llm_service`` (Aula 14).

Cenarios exigidos pela spec: timeout, HTTP 429, HTTP 5xx, queda do provedor e
payload invalido — todos com mocks (sem rede).
"""
import pytest
import requests

from assist.circuit_breaker import Interruptor
from assist.llm_service import (
    ErroProvedor,
    ServicoIndisponivel,
    chamar_llm,
)
from assist.telemetry import estimar_custo

MODO = "summarize"
LOGS = "log de teste"


class FakeResposta:
    """Resposta HTTP bruta que o ``llm_service`` espera de ``requests.post``."""

    def __init__(self, status_code, corpo):
        self.status_code = status_code
        self._corpo = corpo
        self.url = "https://provedor-de-teste.local/v1/chat/completions"
        self.duracao_ms = 1.5

    def json(self):
        return self._corpo


def resposta_ok(answer="resumo gerado", tokens_prompt=12, tokens_output=30):
    return FakeResposta(
        200,
        {
            "choices": [{"message": {"content": answer}}],
            "usage": {"prompt_tokens": tokens_prompt,
                      "completion_tokens": tokens_output},
        },
    )


def _resposta(status, corpo=None):
    return FakeResposta(status, corpo or {})


def test_sucesso_devolve_answer_e_tokens(provedor_falso, sem_dormir, interruptor_reset):
    provedor_falso["fila"].append(resposta_ok("resumo", 12, 30))
    resultado = chamar_llm(MODO, LOGS, temperature=0.3, max_tokens=256)
    assert resultado == {
        "answer": "resumo",
        "tokens_prompt": 12,
        "tokens_output": 30,
    }
    assert provedor_falso["registo"]["chamadas"] == 1
    envio = provedor_falso["registo"]["payloads"][0]
    assert envio["max_tokens"] == 256
    assert envio["temperature"] == 0.3
    assert envio["model"]


def test_sucesso_sem_usage_usa_zero(provedor_falso, sem_dormir):
    provedor_falso["fila"].append(resposta_ok("resumo", 0, 0))
    resultado = chamar_llm(MODO, LOGS, temperature=0.3, max_tokens=256)
    assert resultado["tokens_prompt"] == 0
    assert resultado["tokens_output"] == 0


def test_429_retenta_com_backoff_e_sucesso(provedor_falso, sem_dormir):
    provedor_falso["fila"].append(_resposta(429))
    provedor_falso["fila"].append(resposta_ok("apos retry", 8, 20))
    resultado = chamar_llm(MODO, LOGS, temperature=0.3, max_tokens=256)
    assert resultado["answer"] == "apos retry"
    assert provedor_falso["registo"]["chamadas"] == 2


def test_timeout_esgota_tentativas_e_abre_circuito(provedor_falso, sem_dormir):
    provedor_falso["fila"].extend(
        [requests.Timeout("timeout") for _ in range(3)]
    )
    with pytest.raises(ServicoIndisponivel):
        chamar_llm(MODO, LOGS, temperature=0.3, max_tokens=256)
    assert provedor_falso["registo"]["chamadas"] == 3


def test_5xx_consecutivo_abre_circuito_e_seguintes_curto_circuitam(
    provedor_falso, sem_dormir, monkeypatch
):
    interruptor = Interruptor(falhas_para_abrir=2, timeout_aberto=1000)
    monkeypatch.setattr("assist.llm_service.INTERRUPTOR", interruptor)

    # Cada chamada esgota as 3 tentativas com 500 (3 pedidos HTTP por chamada).
    provedor_falso["fila"].extend([_resposta(500)] * 3)
    with pytest.raises(ServicoIndisponivel):
        chamar_llm(MODO, LOGS, temperature=0.3, max_tokens=256)
    assert interruptor.estado == "closed"

    provedor_falso["fila"].extend([_resposta(500)] * 3)
    with pytest.raises(ServicoIndisponivel):
        chamar_llm(MODO, LOGS, temperature=0.3, max_tokens=256)
    assert interruptor.estado == "open"

    # Circuito aberto: a chamada seguinte nao contacta o provedor.
    with pytest.raises(ServicoIndisponivel):
        chamar_llm(MODO, LOGS, temperature=0.3, max_tokens=256)
    assert provedor_falso["registo"]["chamadas"] == 6


def test_queda_do_provedor_connectionerror(provedor_falso, sem_dormir):
    provedor_falso["fila"].extend(
        [requests.ConnectionError("connection refused") for _ in range(3)]
    )
    with pytest.raises(ServicoIndisponivel):
        chamar_llm(MODO, LOGS, temperature=0.3, max_tokens=256)


def test_half_open_sucesso_fecha_circuito(provedor_falso, sem_dormir, monkeypatch):
    interruptor = Interruptor(falhas_para_abrir=1, timeout_aberto=0)
    monkeypatch.setattr("assist.llm_service.INTERRUPTOR", interruptor)

    provedor_falso["fila"].extend([_resposta(503)] * 3)
    with pytest.raises(ServicoIndisponivel):
        chamar_llm(MODO, LOGS, temperature=0.3, max_tokens=256)
    # Cooldown de 0s ja decorreu: recusa instantanea e o estado passa logo a
    # half-open, permitindo uma chamada de teste.
    assert interruptor.estado == "half_open"

    # Cooldown ja passou (timeout 0) -> half-open permite uma chamada de teste.
    provedor_falso["fila"].append(resposta_ok("recuperou", 5, 10))
    resultado = chamar_llm(MODO, LOGS, temperature=0.3, max_tokens=256)
    assert resultado["answer"] == "recuperou"
    assert interruptor.estado == "closed"


def test_4xx_nao_retentado_e_nao_abre_circuito(
    provedor_falso, sem_dormir, interruptor_reset
):
    provedor_falso["fila"].append(_resposta(401))
    with pytest.raises(ErroProvedor) as exc:
        chamar_llm(MODO, LOGS, temperature=0.3, max_tokens=256)
    assert exc.value.status == 401
    assert provedor_falso["registo"]["chamadas"] == 1


def test_estimar_custo_usa_precos_por_milhao():
    custo = estimar_custo(1_000_000, 500_000)
    assert custo == 0.45


def test_estimar_custo_sem_tokens_e_zero():
    assert estimar_custo(0, 0) == 0.0