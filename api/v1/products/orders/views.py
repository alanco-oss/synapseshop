from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import cache as cache_pedidos
from .mensageria import contrato, metricas, produtor, topicos
from .models import Order
from .serializers import OrderSerializer, PagamentoSimuladoSerializer


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

    @action(detail=False, methods=["get"], url_path="metricas-mensageria")
    def metricas_mensageria(self, request):
        return Response(metricas.resumo())

    @action(detail=True, methods=["post"], url_path="pagar")
    def pagar(self, request, pk=None):
        """Simula o pagamento de um pedido (Aula 11).

        - ``aprovado=true``: transicao ``pending -> paid`` (unica valida),
          invalidacao do cache e publicacao de ``PagamentoSimulado``;
        - ``aprovado=false``: o pedido permanece ``pending`` mas o evento e
          publicado na mesma, para que a notificacao cubra a recusa;
        - pedido num estado que nao ``pending``: ``409``;
        - payload desconhecido/invalido: ``400`` (gerido pelo serializer).
        """
        pagamento = PagamentoSimuladoSerializer(data=request.data)
        pagamento.is_valid(raise_exception=True)
        aprovado = pagamento.validated_data["aprovado"]

        pedido = self.get_object()
        if pedido.status != "pending":
            return Response(
                {
                    "detail": (
                        f"O pedido {pedido.pk} nao esta pendente "
                        f"(status={pedido.status})."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        if aprovado:
            pedido.status = "paid"
            pedido.save(update_fields=["status"])
            cache_pedidos.invalidar_pedido(pedido.pk, "PagamentoAprovado")

        publicado = produtor.publicar_evento(
            contrato.construir_pagamento_simulado(pedido, aprovado),
            topico=topicos.TOPICO_PAGAMENTO,
        )

        corpo = {
            "pedido_id": pedido.pk,
            "status": pedido.status,
            "aprovado": aprovado,
            "evento_publicado": publicado,
        }
        if aprovado:
            return Response(corpo, status=status.HTTP_200_OK)
        return Response(corpo, status=status.HTTP_402_PAYMENT_REQUIRED)

    def perform_create(self, serializer):
        pedido = serializer.save()
        cache_pedidos.invalidar_lista("PedidoCriado")
        produtor.publicar_evento(contrato.construir_pedido_criado(pedido))

    def perform_update(self, serializer):
        serializer.save()
        cache_pedidos.invalidar_pedido(serializer.instance.pk)

    def perform_destroy(self, instance):
        pedido_id = instance.pk
        instance.delete()
        cache_pedidos.invalidar_pedido(pedido_id, "PedidoRemovido")