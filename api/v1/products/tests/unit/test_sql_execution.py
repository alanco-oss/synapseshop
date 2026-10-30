"""Testes da execucao read-only e conversao de resultados (Aula 21)."""

import pytest

from ask_sql.errors import ErroExecucaoSQL
from ask_sql.execution import executar_sql
from orders.models import Order

pytestmark = pytest.mark.django_db


def test_executa_select_e_converte_tipos_para_json():
    Order.objects.create(user_id=1, total="10.50")

    dados = executar_sql(
        "SELECT id, total, status, created_at FROM orders_order",
        [],
    )

    assert dados["columns"] == ["id", "total", "status", "created_at"]
    assert dados["row_count"] == 1
    assert dados["truncated"] is False
    linha = dados["results"][0]
    assert isinstance(linha["total"], float)
    assert isinstance(linha["created_at"], str)


def test_trunca_resultados_acima_do_limite():
    for indice in range(3):
        Order.objects.create(user_id=indice, total="1.00")

    dados = executar_sql(
        "SELECT id FROM orders_order ORDER BY id",
        [],
        max_rows=2,
    )

    assert dados["row_count"] == 2
    assert dados["truncated"] is True


def test_erro_de_execucao_vira_erro_de_dominio():
    with pytest.raises(ErroExecucaoSQL):
        executar_sql("SELECT * FROM tabela_inexistente", [])
