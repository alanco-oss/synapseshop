from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import cache as cache_pedidos
from .models import Order
from .serializers import OrderSerializer


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def list(self, request, *args, **kwargs):
        def carregar():
            return OrderSerializer(self.get_queryset(), many=True).data

        dados = cache_pedidos.buscar_ou_preencher(
            cache_pedidos.chave_lista(),
            cache_pedidos.TTL_LISTA,
            cache_pedidos.ENDPOINT_LISTA,
            carregar,
        )
        return Response(dados)

    @action(detail=True, methods=["get"])
    def detalhes(self, request, pk=None):
        def carregar():
            return OrderSerializer(self.get_object()).data

        dados = cache_pedidos.buscar_ou_preencher(
            cache_pedidos.chave_detalhes(pk),
            cache_pedidos.TTL_DETALHES,
            cache_pedidos.ENDPOINT_DETALHES,
            carregar,
        )
        return Response(dados)

    @action(detail=False, methods=["get"], url_path="metricas-cache")
    def metricas_cache(self, request):
        return Response(cache_pedidos.metricas())

    def perform_create(self, serializer):
        serializer.save()
        cache_pedidos.invalidar_lista("PedidoCriado")

    def perform_update(self, serializer):
        serializer.save()
        cache_pedidos.invalidar_pedido(serializer.instance.pk)

    def perform_destroy(self, instance):
        pedido_id = instance.pk
        instance.delete()
        cache_pedidos.invalidar_pedido(pedido_id, "PedidoRemovido")