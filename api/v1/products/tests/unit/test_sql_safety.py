"""Testes da allow-list e normalizacao da SQL gerada (Aula 21)."""

import pytest

from ask_sql.errors import SQLInseguro, SQLInvalido
from ask_sql.safety import validar_sql


def test_aceita_select_e_injeta_limit():
    sql = validar_sql("SELECT id FROM orders_order", 50, [])
    assert sql == "SELECT id FROM orders_order LIMIT 50"


def test_nao_duplica_limit_existente():
    sql = validar_sql("SELECT id FROM orders_order LIMIT 5", 50, [])
    assert sql.count("LIMIT") == 1


def test_aceita_with_e_cte():
    sql = (
        "WITH ultimos AS (SELECT id FROM orders_order ORDER BY id DESC LIMIT 3) "
        "SELECT id FROM ultimos"
    )
    assert validar_sql(sql, 50, []) == sql


def test_aceita_join_entre_tabelas_permitidas():
    sql = (
        "SELECT i.id, i.nome FROM catalog_item i "
        "JOIN catalog_category c ON c.id = i.categoria_id"
    )
    assert sql.startswith("SELECT")


def test_aceita_params_com_placeholders():
    sql = validar_sql(
        "SELECT id FROM orders_order WHERE status = %s", 50, ["paid"]
    )
    assert "%s" in sql


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders_order",
        "UPDATE orders_order SET status = 'paid'",
        "INSERT INTO orders_order (total) VALUES (1)",
        "DROP TABLE orders_order",
        "ALTER TABLE orders_order ADD COLUMN x int",
        "TRUNCATE orders_order",
        "CREATE TABLE x (id int)",
        "SELECT id FROM orders_order; DROP TABLE orders_order",
    ],
)
def test_rejeita_comandos_de_escrita(sql):
    with pytest.raises(SQLInseguro):
        validar_sql(sql, 50, [])


def test_rejeita_comentarios():
    with pytest.raises(SQLInseguro):
        validar_sql("SELECT id FROM orders_order -- escondido", 50, [])


def test_rejeita_tabela_fora_da_allow_list():
    with pytest.raises(SQLInseguro):
        validar_sql("SELECT id FROM users", 50, [])


def test_rejeita_coluna_sensivel():
    with pytest.raises(SQLInseguro):
        validar_sql("SELECT senha_hash FROM orders_order", 50, [])


def test_rejeita_placeholder_sem_param():
    with pytest.raises(SQLInvalido):
        validar_sql("SELECT id FROM orders_order WHERE status = %s", 50, [])


def test_rejeita_sql_vazio():
    with pytest.raises(SQLInvalido):
        validar_sql("   ", 50, [])


def test_rejeita_select_into():
    with pytest.raises(SQLInseguro):
        validar_sql("SELECT id INTO nova_tabela FROM orders_order", 50, [])
