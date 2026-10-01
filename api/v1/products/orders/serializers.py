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