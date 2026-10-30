"""Testes do prompt Texto-para-SQL (Aula 21)."""

from ask_sql.prompts import montar_mensagens_sql
from ask_sql.schema import construir_schema_ddl


def test_schema_contem_apenas_tabelas_permitidas():
    ddl = construir_schema_ddl()
    assert "orders_order" in ddl
    assert "catalog_item" in ddl
    assert "catalog_category" in ddl
    assert "users" not in ddl
    assert "tokens" not in ddl


def test_schema_nao_expoe_colunas_sensiveis():
    ddl = construir_schema_ddl().lower()
    assert "senha_hash" not in ddl
    assert "password" not in ddl


def test_schema_documenta_colunas_do_dominio():
    ddl = construir_schema_ddl()
    assert "user_id" in ddl
    assert "status" in ddl
    assert "total" in ddl
    assert "created_at" in ddl
    assert "categoria_id" in ddl


def test_mensagens_incluem_schema_regras_e_pergunta():
    ddl = construir_schema_ddl()
    mensagens = montar_mensagens_sql("Quais os 5 ultimos pedidos?", ddl)
    assert mensagens[0]["role"] == "system"
    assert "SELECT" in mensagens[0]["content"]
    assert "orders_order" in mensagens[0]["content"]
    assert '"sql"' in mensagens[0]["content"]
    assert mensagens[1]["role"] == "user"
    assert "Quais os 5 ultimos pedidos?" in mensagens[1]["content"]


def test_mensagens_injetam_limite_maximo():
    mensagens = montar_mensagens_sql("x", "schema")
    assert "__MAX_ROWS__" not in mensagens[0]["content"]
