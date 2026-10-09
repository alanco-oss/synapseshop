from rest_framework import viewsets

from products.api_conventions import aplicar_filtros, aplicar_ordenacao

from .models import Category, Item
from .serializers import CategorySerializer, ItemSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    ordenacao_padrao = "nome"
    mapa_filtros = {}
    mapa_ordenacao = {"nome": "nome", "id": "id"}

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = aplicar_filtros(queryset, self.request, self.mapa_filtros)
        return aplicar_ordenacao(
            queryset, self.request, self.mapa_ordenacao, self.ordenacao_padrao
        )


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    ordenacao_padrao = "nome"
    mapa_filtros = {"categoria": "categoria_id"}
    mapa_ordenacao = {
        "nome": "nome",
        "preco": "preco",
        "estoque": "estoque",
        "id": "id",
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = aplicar_filtros(queryset, self.request, self.mapa_filtros)
        return aplicar_ordenacao(
            queryset, self.request, self.mapa_ordenacao, self.ordenacao_padrao
        )
