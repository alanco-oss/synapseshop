from rest_framework import serializers

from .models import Order


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["id", "user_id", "status", "total", "created_at"]
        read_only_fields = ["created_at"]

    def validate_total(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "O total do pedido deve ser um valor não negativo."
            )
        return value


class PagamentoSimuladoSerializer(serializers.Serializer):
    """Payload do ``POST /api/v1/pedidos/{id}/pagar/`` (Aula 11)."""

    aprovado = serializers.BooleanField(
        default=True,
        help_text="Resultado da simulacao: true aprova, false recusa.",
    )

    def validate(self, attrs):
        permitidos = set(self.fields)
        desconhecidos = set(self.initial_data) - permitidos
        if desconhecidos:
            raise serializers.ValidationError(
                dict.fromkeys(sorted(desconhecidos), "Campo desconhecido no payload de pagamento.")
            )
        return attrs
