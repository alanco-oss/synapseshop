"""Templates de prompt do assistente (Aula 14).

Dois modos, gerando um array de ``messages`` compatível com o endpoint
``/chat/completions``: a instrução no papel do ``system`` e o conteúdo dos
logs (já redigido) no ``user``.
"""

MODO_SUMMARIZE = "summarize"
MODO_EXPLAIN = "explain"
MODOS = (MODO_SUMMARIZE, MODO_EXPLAIN)

_SISTEMA_SUMMARIZE = (
    "És um assistente de suporte a engenharia. Resume o log abaixo num texto "
    "curto, em português, destacando erros, causas prováveis e recomendações "
    "de ação. Não inventes factos que não estejam no log."
)

_SISTEMA_EXPLAIN = (
    "És um assistente de suporte a engenharia. Explica o log abaixo em "
    "linguagem simples, em português, indicando o que aconteceu, por que é "
    "relevante e que próximos passos sugeres. Não inventes factos que não "
    "estejam no log."
)

_SISTEMAS = {
    MODO_SUMMARIZE: _SISTEMA_SUMMARIZE,
    MODO_EXPLAIN: _SISTEMA_EXPLAIN,
}

CONTEXTO = (
    "Conteúdo do log (dados sensíveis já redigidos):\n\n{logs}"
)


def montar_mensagens(mode, logs_redigidos):
    """Monta ``messages`` para ``/chat/completions`` a partir do modo e dos
    logs já redigidos."""
    return [
        {"role": "system", "content": _SISTEMAS[mode]},
        {"role": "user", "content": CONTEXTO.format(logs=logs_redigidos)},
    ]
