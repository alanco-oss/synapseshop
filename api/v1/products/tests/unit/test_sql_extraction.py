"""Testes da extracao da resposta da LLM (Aula 21)."""

import pytest

from ask_sql.errors import RespostaInvalida
from ask_sql.extraction import extrair_sql


def test_extrai_json_puro():
    sql, params = extrair_sql(
        '{"sql": "SELECT id FROM orders_order LIMIT 5", "params": []}'
    )
    assert sql == "SELECT id FROM orders_order LIMIT 5"
    assert params == []


def test_extrai_json_com_params():
    sql, params = extrair_sql(
        '{"sql": "SELECT id FROM orders_order WHERE status = %s", "params": ["paid"]}'
    )
    assert params == ["paid"]
    assert "%s" in sql


def test_extrai_json_dentro_de_bloco_markdown():
    texto = '```json\n{"sql": "SELECT 1", "params": []}\n```'
    assert extrair_sql(texto) == ("SELECT 1", [])


def test_extrai_sql_dentro_de_bloco_markdown():
    texto = "```sql\nSELECT id FROM orders_order\n```"
    assert extrair_sql(texto) == ("SELECT id FROM orders_order", [])


def test_extrai_sql_puro():
    assert extrair_sql("SELECT id FROM orders_order") == (
        "SELECT id FROM orders_order",
        [],
    )


def test_extrai_json_com_texto_em_volta():
    texto = 'Aqui esta:\n{"sql": "SELECT 1", "params": []}\nFim.'
    assert extrair_sql(texto) == ("SELECT 1", [])


def test_resposta_vazia_falha():
    with pytest.raises(RespostaInvalida):
        extrair_sql("   ")


def test_resposta_sem_sql_falha():
    with pytest.raises(RespostaInvalida):
        extrair_sql("Nao sei responder.")


def test_params_invalido_falha():
    with pytest.raises(RespostaInvalida):
        extrair_sql('{"sql": "SELECT 1", "params": {"a": 1}}')
