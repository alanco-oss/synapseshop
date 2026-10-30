"""Execucao segura da SQL gerada (Aula 21).

A validacao em ``safety.py`` e a primeira barreira. Esta camada adiciona:

- transacao read-only no PostgreSQL (``SET TRANSACTION READ ONLY``);
- ``statement_timeout`` configuravel;
- ``PRAGMA query_only`` no SQLite (testes);
- limite de linhas devolvidas;
- conversao de tipos do banco para JSON.
"""

import base64
import datetime
import decimal
import uuid

from django.db import DatabaseError, connection, transaction

from . import config
from .errors import ErroExecucaoSQL


def _json_safe(valor):
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    if isinstance(valor, decimal.Decimal):
        return float(valor)
    if isinstance(valor, (datetime.datetime, datetime.date, datetime.time)):
        return valor.isoformat()
    if isinstance(valor, uuid.UUID):
        return str(valor)
    if isinstance(valor, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(valor)).decode("ascii")
    return str(valor)


def _nomes_colunas(description):
    nomes = []
    ocorrencias = {}
    for coluna in description:
        nome = coluna[0]
        ocorrencias[nome] = ocorrencias.get(nome, 0) + 1
        if ocorrencias[nome] > 1:
            nome = f"{nome}_{ocorrencias[nome]}"
        nomes.append(nome)
    return nomes


def _mensagem_erro(exc):
    detalhe = str(exc).strip() or exc.__class__.__name__
    return f"Nao foi possivel executar a consulta: {detalhe[:300]}"


def executar_sql(sql, params, max_rows=None):
    """Executa a consulta e devolve ``columns/results/row_count/truncated``."""
    limite = max(int(max_rows or config.ASK_SQL_MAX_ROWS), 1)
    params = list(params or [])
    vendor = connection.vendor
    ja_em_transacao = connection.in_atomic_block
    pragma_sqlite = False

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                if vendor == "postgresql" and not ja_em_transacao:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute(
                        "SET LOCAL statement_timeout = "
                        f"{int(config.ASK_SQL_TIMEOUT_MS)}"
                    )
                elif vendor == "sqlite":
                    cursor.execute("PRAGMA query_only = ON")
                    pragma_sqlite = True

                cursor.execute(sql, params)
                if not cursor.description:
                    return {
                        "columns": [],
                        "results": [],
                        "row_count": 0,
                        "truncated": False,
                    }

                colunas = _nomes_colunas(cursor.description)
                linhas = cursor.fetchmany(limite + 1)
    except DatabaseError as exc:
        raise ErroExecucaoSQL(_mensagem_erro(exc)) from exc
    finally:
        if pragma_sqlite:
            try:
                with connection.cursor() as cursor_reset:
                    cursor_reset.execute("PRAGMA query_only = OFF")
            except Exception:
                pass

    truncado = len(linhas) > limite
    linhas = linhas[:limite]
    resultados = [
        {
            coluna: _json_safe(valor)
            for coluna, valor in zip(colunas, linha, strict=False)
        }
        for linha in linhas
    ]

    return {
        "columns": colunas,
        "results": resultados,
        "row_count": len(resultados),
        "truncated": truncado,
    }
