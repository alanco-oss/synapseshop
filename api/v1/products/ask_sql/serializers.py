from rest_framework import serializers

from . import config


class AskSqlSerializer(serializers.Serializer):
    """Payload do ``POST /api/v1/ask_sql`` (Aula 21)."""

    question = serializers.CharField(
        max_length=config.ASK_SQL_MAX_QUESTION_LENGTH,
        trim_whitespace=True,
    )
    temperature = serializers.FloatField(
        min_value=0.0,
        max_value=1.0,
        default=config.ASK_SQL_TEMPERATURE,
    )
    max_tokens = serializers.IntegerField(
        min_value=1,
        max_value=4096,
        default=config.ASK_SQL_DEFAULT_MAX_TOKENS,
    )

    def validate(self, attrs):
        permitidos = set(self.fields)
        desconhecidos = set(self.initial_data) - permitidos
        if desconhecidos:
            raise serializers.ValidationError(
                dict.fromkeys(
                    sorted(desconhecidos),
                    "Campo desconhecido no payload do ask_sql.",
                )
            )
        return attrs
