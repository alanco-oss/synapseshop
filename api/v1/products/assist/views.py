"""Endpoint ``POST /api/v1/assist`` (Aula 14).

Fluxo: valida o payload (RFC 7807 via ``products.exceptions``), redige os
dados sensiveis, chama o ``llm_service`` com tolerância a falhas e devolve a
resposta gerada mais os metadados de consumo.
"""
import logging
import time

from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from . import redaction
from .llm_service import ErroProvedor, ServicoIndisponivel, chamar_llm
from .serializers import AssistSerializer

logger = logging.getLogger("assist")


class AssistenteIndisponivel(APIException):
    status_code = 503
    default_detail = "O assistente está indisponível no momento."
    default_code = "servico_indisponivel"


class ProvedorIndisponivel(APIException):
    status_code = 502
    default_detail = "O provedor de LLM devolveu um erro."
    default_code = "provedor_invalido"


class AssistView(APIView):
    def post(self, request):
        serializer = AssistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dados = serializer.validated_data
        logs_redigidos = redaction.redigir_logs(dados["logs"])

        inicio = time.monotonic()
        try:
            resultado = chamar_llm(
                mode=dados["mode"],
                logs_redigidos=logs_redigidos,
                temperature=dados["temperature"],
                max_tokens=dados["max_tokens"],
            )
            duracao_ms = round((time.monotonic() - inicio) * 1000, 2)
        except ServicoIndisponivel as exc:
            duracao_ms = round((time.monotonic() - inicio) * 1000, 2)
            logger.warning(
                "acao=endpoint_assistir status=falha erro=servico_indisponivel "
                "duracao_ms=%s motivo=%s",
                duracao_ms,
                exc.motivo,
            )
            raise AssistenteIndisponivel(exc.motivo) from exc
        except ErroProvedor as exc:
            duracao_ms = round((time.monotonic() - inicio) * 1000, 2)
            logger.warning(
                "acao=endpoint_assistir status=falha erro=provedor "
                "duracao_ms=%s http=%s",
                duracao_ms,
                exc.status,
            )
            raise ProvedorIndisponivel(
                f"O provedor de LLM devolveu um erro (HTTP {exc.status})."
            ) from exc

        logger.info(
            "acao=endpoint_assistir status=sucesso duracao_ms=%.2f",
            duracao_ms,
        )
        return Response(
            {
                "answer": resultado["answer"],
                "meta": {
                    "tokens_prompt": resultado["tokens_prompt"],
                    "tokens_output": resultado["tokens_output"],
                },
            }
        )
