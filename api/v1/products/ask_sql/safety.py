"""Validacao da SQL gerada pela LLM (Aula 21).

Defesa em profundidade antes de tocar no banco:

- apenas uma instrucao, comecada por ``SELECT`` ou ``WITH``;
- sem comentarios (podem esconder comandos);
- allow-list de palavras proibidas (DML/DDL/administracao);
- allow-list de tabelas (``schema.TABELAS_PERMITIDAS``);
- bloqueio de colunas sensiveis;
- ``LIMIT`` injetado quando ausente;
- placeholders ``%s`` compativeis com a lista de ``params``.
"""

import re

import sqlparse
from sqlparse import tokens as T

from .errors import SQLInseguro, SQLInvalido
from .schema import COLUNAS_SENSIVEIS, TABELAS_PERMITIDAS

MAX_SQL_LENGTH = 20000

PALAVRAS_PROIBIDAS = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "TRUNCATE",
        "CREATE",
        "GRANT",
        "REVOKE",
        "COPY",
        "CALL",
        "DO",
        "MERGE",
        "VACUUM",
        "ANALYZE",
        "REINDEX",
        "CLUSTER",
        "REFRESH",
        "LOCK",
        "SET",
        "RESET",
        "BEGIN",
        "COMMIT",
        "ROLLBACK",
        "SAVEPOINT",
        "INTO",
        "EXECUTE",
        "RETURNING",
    }
)

_PROIBIDAS_RE = re.compile(
    r"\b(" + "|".join(sorted(PALAVRAS_PROIBIDAS)) + r")\b", re.IGNORECASE
)

_TABELA_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+[\"'`\[]?(?:([A-Za-z_][\w$]*)\.)?"
    r"([A-Za-z_][\w$]*)[\"'`\]]?",
    re.IGNORECASE,
)

_CTE_RE = re.compile(
    r"(?:\bWITH\b|,)\s*([A-Za-z_][\w$]*)\s+AS\s*\(", re.IGNORECASE
)

_PLACEHOLDER_RE = re.compile(r"%s")
_LIMIT_RE = re.compile(r"\bLIMIT\b", re.IGNORECASE)


def _primeira_palavra(statement):
    for token in statement.tokens:
        if token.is_whitespace or token.ttype in T.Comment:
            continue
        return token.value.upper()
    return ""


def _garantir_sem_comentarios(statement):
    for token in statement.flatten():
        if token.ttype in T.Comment:
            raise SQLInseguro("Comentarios nao sao permitidos na consulta gerada.")


def _validar_tabelas(sql):
    ctes = {nome.lower() for nome in _CTE_RE.findall(sql)}
    permitidas = {tabela.lower() for tabela in TABELAS_PERMITIDAS} | ctes

    for _esquema, tabela in _TABELA_RE.findall(sql):
        if tabela and tabela.lower() not in permitidas:
            raise SQLInseguro(
                f"Tabela nao permitida na consulta: {tabela}."
            )


def _validar_colunas_sensiveis(sql):
    for coluna in COLUNAS_SENSIVEIS:
        if re.search(rf"\b{re.escape(coluna)}\b", sql, re.IGNORECASE):
            raise SQLInseguro(
                f"Coluna sensivel nao pode ser consultada: {coluna}."
            )


def validar_sql(sql, max_rows, params):
    """Valida/normaliza a SQL e devolve a instrucao pronta a executar."""
    if not isinstance(sql, str) or not sql.strip():
        raise SQLInvalido("A consulta gerada esta vazia.")

    sql = sql.strip()
    if len(sql) > MAX_SQL_LENGTH:
        raise SQLInvalido("A consulta gerada excede o tamanho maximo permitido.")

    if sql.endswith(";"):
        sql = sql[:-1].rstrip()

    if len(sqlparse.split(sql)) != 1:
        raise SQLInseguro("Apenas uma instrucao SQL e permitida.")

    statements = sqlparse.parse(sql)
    if len(statements) != 1:
        raise SQLInseguro("Apenas uma instrucao SQL e permitida.")

    statement = statements[0]
    _garantir_sem_comentarios(statement)

    primeira = _primeira_palavra(statement)
    if primeira not in ("SELECT", "WITH"):
        raise SQLInseguro("Apenas consultas SELECT (ou WITH ... SELECT) sao permitidas.")

    if _PROIBIDAS_RE.search(sql):
        palavra = _PROIBIDAS_RE.search(sql).group(1).upper()
        raise SQLInseguro(f"Comando nao permitido na consulta: {palavra}.")

    _validar_tabelas(sql)
    _validar_colunas_sensiveis(sql)

    if not isinstance(params, list):
        raise SQLInvalido("'params' deve ser uma lista.")

    marcadores = len(_PLACEHOLDER_RE.findall(sql))
    if marcadores != len(params):
        raise SQLInvalido(
            "A quantidade de placeholders %s nao corresponde a lista de params."
        )

    if not _LIMIT_RE.search(sql):
        limite = max(int(max_rows), 1)
        sql = f"{sql} LIMIT {limite}"

    return sql
