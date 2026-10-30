"""Configuracao do endpoint Texto-para-SQL (Aula 21).

Os limites de execucao sao parametrizaveis por variavel de ambiente, seguindo
o mesmo padrao de ``assist.config``.
"""

import os


def _int_env(nome, padrao):
    try:
        return int(os.getenv(nome, str(padrao)))
    except ValueError:
        return padrao


# Pergunta e geracao
ASK_SQL_MAX_QUESTION_LENGTH = _int_env("ASK_SQL_MAX_QUESTION_LENGTH", 1000)
ASK_SQL_DEFAULT_MAX_TOKENS = _int_env("ASK_SQL_DEFAULT_MAX_TOKENS", 512)
ASK_SQL_TEMPERATURE = 0.0

# Execucao segura
ASK_SQL_MAX_ROWS = _int_env("ASK_SQL_MAX_ROWS", 100)
ASK_SQL_TIMEOUT_MS = _int_env("ASK_SQL_TIMEOUT_MS", 5000)
