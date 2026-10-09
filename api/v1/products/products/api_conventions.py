"""Convenções transversais da API (Aula 13).

Centraliza paginação, filtros e ordenação para que todos os recursos sigam a
mesma nomenclatura documentada no contrato OpenAPI:

- paginação **opcional** por ``?page=`` e ``?limit=``; sem esses parâmetros a
  coleção inteira continua a ser devolvida como uma lista simples, preservando
  o contrato anterior à Aula 13;
- filtros por igualdade em campos declarados (ex.: ``?status=pending``);
- ordenação ``?sort=campo:asc|desc`` (ex.: ``?sort=createdAt:desc``).

Os parâmetros são validados contra listas explícitas (nunca interpolam
colunas arbitrárias no ORM), pelo que valores desconhecidos são simplesmente
ignorados — a API mantém a ordenação por omissão.
"""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class PaginacaoPadrao(PageNumberPagination):
    """Paginação por número de página, ativada apenas quando solicitada."""

    page_query_param = "page"
    page_size_query_param = "limit"
    page_size = 20
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        pedida = "page" in request.query_params or "limit" in request.query_params
        if not pedida:
            return None
        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data):
        proxima_pagina = self.page.next_page_number() if self.page.has_next() else None
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "nextCursor": proxima_pagina,
                "results": data,
            }
        )


def aplicar_ordenacao(queryset, request, mapa, padrao=None):
    """Aplica ``?sort=campo:asc|desc`` usando apenas campos do ``mapa``."""
    parametro = request.query_params.get("sort")
    campo, _, direcao = parametro.partition(":") if parametro else ("", "", "")
    alvo = mapa.get(campo) if campo else None
    if alvo:
        return queryset.order_by(f"-{alvo}" if direcao.lower() == "desc" else alvo)
    return queryset.order_by(padrao) if padrao else queryset


def aplicar_filtros(queryset, request, mapa):
    """Aplica filtros de igualdade para os parâmetros declarados no ``mapa``."""
    for parametro, campo in mapa.items():
        valor = request.query_params.get(parametro)
        if valor not in (None, ""):
            queryset = queryset.filter(**{campo: valor})
    return queryset
