"""Testes das convenções transversais da API (Aula 13)."""
from unittest import mock

from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from products.api_conventions import (
    PaginacaoPadrao,
    aplicar_filtros,
    aplicar_ordenacao,
)

factory = APIRequestFactory()


def _request(query=""):
    return Request(factory.get(f"/api/v1/pedidos/{query}"))


def test_ordenacao_sem_parametro_usa_padrao():
    queryset = mock.MagicMock()

    aplicar_ordenacao(queryset, _request(), {"total": "total"}, "-created_at")

    queryset.order_by.assert_called_once_with("-created_at")


def test_ordenacao_sem_parametro_e_sem_padrao_devolve_queryset():
    queryset = mock.MagicMock()

    resultado = aplicar_ordenacao(queryset, _request(), {"total": "total"})

    assert resultado is queryset
    queryset.order_by.assert_not_called()


def test_ordenacao_desc_mapeia_para_campo_negativo():
    queryset = mock.MagicMock()

    aplicar_ordenacao(queryset, _request("?sort=createdAt:desc"), {"createdAt": "created_at"})

    queryset.order_by.assert_called_once_with("-created_at")


def test_ordenacao_asc_mapeia_para_campo_direto():
    queryset = mock.MagicMock()

    aplicar_ordenacao(queryset, _request("?sort=total:asc"), {"total": "total"})

    queryset.order_by.assert_called_once_with("total")


def test_ordenacao_campo_desconhecido_cai_no_padrao():
    queryset = mock.MagicMock()

    aplicar_ordenacao(queryset, _request("?sort=inexistente:desc"), {"total": "total"}, "id")

    queryset.order_by.assert_called_once_with("id")


def test_filtros_aplica_apenas_parametros_presentes():
    queryset = mock.MagicMock()

    aplicar_filtros(
        queryset,
        _request("?status=paid&user_id="),
        {"status": "status", "user_id": "user_id"},
    )

    queryset.filter.assert_called_once_with(status="paid")


def test_paginacao_nao_ativa_sem_parametros():
    assert PaginacaoPadrao().paginate_queryset([1, 2, 3], _request()) is None


def test_paginacao_ativa_com_page_e_limit():
    paginacao = PaginacaoPadrao()

    pagina = paginacao.paginate_queryset(list(range(5)), _request("?page=1&limit=2"))

    assert len(pagina) == 2


def test_envelope_paginado_expoe_next_cursor():
    paginacao = PaginacaoPadrao()
    paginacao.paginate_queryset(list(range(5)), _request("?page=1&limit=2"))

    corpo = paginacao.get_paginated_response([{"id": 0}, {"id": 1}]).data

    assert set(corpo) == {"count", "next", "previous", "nextCursor", "results"}
    assert corpo["count"] == 5
    assert corpo["nextCursor"] == 2
