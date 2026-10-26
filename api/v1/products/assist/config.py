"""Configuracao do provedor de LLM (Aula 14).

Todos os limites do ``llm_service`` sao parametrizaveis por variavel de
ambiente, seguindo o padrao ja usado no projeto (``health.py`` le env
directamente):
"""

import os


def _float_env(nome, padrao):
    try:
        return float(os.getenv(nome, str(padrao)))
    except ValueError:
        return padrao


def _int_env(nome, padrao):
    try:
        return int(os.getenv(nome, str(padrao)))
    except ValueError:
        return padrao


LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Resiliência (spec: timeout <= 5s, 3 tentativas, backoff exp + jitter)
LLM_TIMEOUT = _float_env("LLM_TIMEOUT", 5.0)
LLM_RETRIES = _int_env("LLM_RETRIES", 3)
LLM_BACKOFF_BASE = _float_env("LLM_BACKOFF_BASE", 0.5)
LLM_BACKOFF_JITTER = _float_env("LLM_BACKOFF_JITTER", 0.5)
LLM_BACKOFF_MAXIMO = _float_env("LLM_BACKOFF_MAXIMO", 5.0)

# Circuit breaker (closed -> open -> half-open -> closed)
LLM_CIRCUIT_FALHAS_PARA_ABRIR = _int_env("LLM_CIRCUIT_FALHAS_PARA_ABRIR", 3)
LLM_CIRCUIT_TIMEOUT_ABERTO = _float_env("LLM_CIRCUIT_TIMEOUT_ABERTO", 30.0)

# Estimativa de custo (USD por 1M de tokens)
LLM_PRECO_INPUT_1M = _float_env("LLM_PRECO_INPUT_1M", 0.15)
LLM_PRECO_OUTPUT_1M = _float_env("LLM_PRECO_OUTPUT_1M", 0.60)

DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 256
