from rest_framework import serializers

from .models import Category, Item


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "nome", "descricao"]


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "nome", "descricao", "preco", "estoque", "categoria"]

    def validate_preco(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "O preço deve ser um valor não negativo."
            )
        return value
