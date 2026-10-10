"""Servico de comunicacao com o provedor de LLM (Aula 14).

Implementa a resiliencia exigida pela spec:

- **timeout** por tentativa (``LLM_TIMEOUT``, <= 5s);
- **retry** com *backoff* exponencial + *jitter* (``LLM_RETRIES``
  tentativas, ``LLM_BACKOFF_BASE * 2**(n-1) + jitter``);
- **circuit breaker** (closed/open/half-open) que, aberto, recusa chamadas
  sem sequer contactar o provedor.

Sao retentados apenas erros transitórios (HTTP 429, erros 5xx, timeout e
falhas de rede). Erros 4xx (exceto 429) falham imediatamente porque ja sao
deterministicos do lado do pedido ou da autenticacao.
"""
import logging
import random
import time

import requests

from . import config, prompts
from .circuit_breaker import INTERRUPTOR
from .telemetry import registrar_chamada

logger = logging.getLogger("assist")


class ErroProvedor(Exception):
    """Falha determinística na resposta do provedor (4xx exceto 429)."""

    def __init__(self, status):
        super().__init__(f"Erro do provedor de LLM (HTTP {status}).")
        self.status = status


class ServicoIndisponivel(Exception):
    """Provedor indisponivel: retentativas esgotadas ou circuito aberto."""

    def __init__(self, motivo):
        super().__init__(motivo)
        self.motivo = motivo


def _sao_transitorios(exc, status):
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    return status in (429, *range(500, 600))


def _backoff(tentativa):
    base = config.LLM_BACKOFF_BASE * (2 ** (tentativa - 1))
    jitter = random.uniform(0, config.LLM_BACKOFF_JITTER)
    return min(base + jitter, config.LLM_BACKOFF_MAXIMO)


def _dormir(tentativa):
    time.sleep(_backoff(tentativa))


def _requisicao(messages, temperature, max_tokens):
    """Uma unica tentativa junto ao provedor. Devolve a resposta HTTP bruta."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.LLM_API_KEY}",
    }
    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    inicio = time.monotonic()
    resposta = requests.post(
        f"{config.LLM_BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        timeout=config.LLM_TIMEOUT,
    )
    resposta.duracao_ms = round((time.monotonic() - inicio) * 1000, 2)
    return resposta


def _procesar_sucesso(resposta):
    corpo = resposta.json()
    conteudo = corpo["choices"][0]["message"]["content"]
    uso = corpo.get("usage", {})
    return {
        "answer": conteudo,
        "tokens_prompt": uso.get("prompt_tokens", 0),
        "tokens_output": uso.get("completion_tokens", 0),
    }


def chamar_llm(mode, logs_redigidos, temperature, max_tokens):
    """Chamada resiliente ao provedor.

    Devolve ``{"answer", "tokens_prompt", "tokens_output"}``. Levanta
    ``ErroProvedor`` para 4xx deterministicos e ``ServicoIndisponivel`` quando
    o circuito esta aberto ou as retentativas esgotam.
    """
    if not INTERRUPTOR.permitir():
        registar_bloqueio()
        raise ServicoIndisponivel(
            "O assistente esta indisponivel (circuito aberto). Tente mais tarde."
        )

    messages = prompts.montar_mensagens(mode, logs_redigidos)
    ultima_falha = None
    tentativas = config.LLM_RETRIES

    for tentativa in range(1, tentativas + 1):
        try:
            resposta = _requisicao(messages, temperature, max_tokens)
        except (requests.Timeout, requests.ConnectionError) as exc:
            ultima_falha = type(exc).__name__
            registrar_chamada(tentativa, tentativas, "falha", erro=ultima_falha)
            if tentativa < tentativas:
                _dormir(tentativa)
            continue

        status = resposta.status_code
        if status == 200:
            resultado = _procesar_sucesso(resposta)
            INTERRUPTOR.registrar_sucesso()
            registrar_chamada(
                tentativa,
                tentativas,
                "sucesso",
                duracao_ms=resposta.duracao_ms,
                tokens_prompt=resultado["tokens_prompt"],
                tokens_output=resultado["tokens_output"],
            )
            return resultado

        if not _sao_transitorios(None, status):
            raise ErroProvedor(status)

        ultima_falha = f"HTTP {status}"
        registrar_chamada(
            tentativa,
            tentativas,
            "falha",
            duracao_ms=resposta.duracao_ms,
            erro=ultima_falha,
        )
        if tentativa < tentativas:
            _dormir(tentativa)

    INTERRUPTOR.registrar_falha()
    raise ServicoIndisponivel(
        f"O provedor de LLM nao respondeu apos {tentativas} tentativas "
        f"({ultima_falha})."
    )


def registar_bloqueio():
    logger.warning("acao=assistir status=bloqueado circuito=open modo=short-circuit")