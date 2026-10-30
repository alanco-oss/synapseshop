"""Extracao robusta da SQL devolvida pela LLM (Aula 21).

Formatos aceites, por ordem de preferencia:

1. JSON puro: ``{"sql": "...", "params": []}``
2. JSON dentro de bloco markdown (`` ```json ... ``` ``)
3. Bloco markdown com SQL puro (`` ```sql ... ``` ``)
4. SQL puro comecado por ``SELECT``/``WITH``

Qualquer outro formato levanta ``RespostaInvalida``.
"""

import json
import re

from .errors import RespostaInvalida

_FENCE = re.compile(r"```(?:json|sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_CHAVES_SQL = ("sql", "query", "consulta")
_CHAVES_PARAMS = ("params", "parameters", "parametros")


def _tentar_json(texto):
    try:
        return json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return None


def _normalizar(dados):
    if isinstance(dados, str):
        sql, params = dados, []
    elif isinstance(dados, dict):
        sql = next((dados[chave] for chave in _CHAVES_SQL if dados.get(chave)), None)
        params = next(
            (dados[chave] for chave in _CHAVES_PARAMS if chave in dados),
            [],
        )
        if params is None:
            params = []
    else:
        raise RespostaInvalida(
            "A resposta do modelo deve ser um objeto JSON com a chave 'sql'."
        )

    if not isinstance(sql, str) or not sql.strip():
        raise RespostaInvalida("A resposta do modelo nao contem uma instrucao SQL.")

    if not isinstance(params, list):
        raise RespostaInvalida("'params' deve ser uma lista.")

    for valor in params:
        if isinstance(valor, dict):
            raise RespostaInvalida("Cada valor de 'params' deve ser um valor simples.")

    return sql.strip(), params


def extrair_sql(texto):
    """Devolve ``(sql, params)`` a partir do conteudo textual da resposta."""
    if not isinstance(texto, str) or not texto.strip():
        raise RespostaInvalida("A resposta do modelo esta vazia.")

    bruto = texto.strip()

    dados = _tentar_json(bruto)
    if dados is not None:
        return _normalizar(dados)

    bloco = _FENCE.search(bruto)
    if bloco:
        conteudo = bloco.group(1).strip()
        dados = _tentar_json(conteudo)
        if dados is not None:
            return _normalizar(dados)
        if conteudo.lower().startswith(("select", "with")):
            return _normalizar(conteudo)

    inicio, fim = bruto.find("{"), bruto.rfind("}")
    if inicio != -1 and fim > inicio:
        dados = _tentar_json(bruto[inicio : fim + 1])
        if dados is not None:
            return _normalizar(dados)

    if bruto.lower().startswith(("select", "with")):
        return _normalizar(bruto)

    raise RespostaInvalida(
        "A resposta do modelo nao contem uma consulta SQL reconhecivel."
    )
