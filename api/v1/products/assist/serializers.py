from rest_framework import serializers

from . import config
from .prompts import MODOS


class CampoLogs(serializers.Field):
    """Aceita ``string`` ou ``list[str]`` (a spec permite ambos)."""

    def to_internal_value(self, data):
        if isinstance(data, str):
            return data
        if isinstance(data, list) and all(isinstance(linha, str) for linha in data):
            return data
        raise serializers.ValidationError(
            "'logs' deve ser uma string ou uma lista de strings."
        )

    def to_representation(self, value):
        return value


class AssistSerializer(serializers.Serializer):
    """Payload do ``POST /api/v1/assist`` (Aula 14)."""

    mode = serializers.ChoiceField(choices=MODOS)
    logs = CampoLogs()
    temperature = serializers.FloatField(
        min_value=0.0,
        max_value=1.0,
        default=config.DEFAULT_TEMPERATURE,
    )
    max_tokens = serializers.IntegerField(
        min_value=1,
        default=config.DEFAULT_MAX_TOKENS,
    )

    def validate(self, attrs):
        permitidos = set(self.fields)
        desconhecidos = set(self.initial_data) - permitidos
        if desconhecidos:
            raise serializers.ValidationError(
                {
                    campo: "Campo desconhecido no payload do assistente."
                    for campo in sorted(desconhecidos)
                }
            )
        return attrs