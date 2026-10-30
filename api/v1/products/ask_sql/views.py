"""Endpoint ``POST /api/v1/ask_sql`` (Aula 21).

Fluxo: valida o payload, redige PII da pergunta, injeta o schema no prompt,
chama a LLM com a resiliencia da Aula 14, extrai/valida a SQL e executa em modo
read-only com limite de linhas.
"""

import logging
import time

from rest_framework.response import Response
from rest_framework.views import APIView

from assist import redaction
from assist.llm_service import (
    ErroProvedor,
    ServicoIndisponivel,
    chamar_llm_com_mensagens,
)

from . import config, execution, extraction, prompts, safety, schema
from .errors import ErroConsultaSQL
from .exceptions import (
    ConsultaIndisponivel,
    ProvedorIndisponivel,
    SQLEntidadeInvalida,
)
from .serializers import AskSqlSerializer

logger = logging.getLogger("assist")


class AskSqlView(APIView):
    def post(self, request):
        serializer = AskSqlSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dados = serializer.validated_data
        pergunta = redaction.redigir(dados["question"])
        schema_ddl = schema.construir_schema_ddl()
        messages = prompts.montar_mensagens_sql(pergunta, schema_ddl)

        inicio_llm = time.monotonic()
        try:
            resultado = chamar_llm_com_mensagens(
                messages,
                dados["temperature"],
                dados["max_tokens"],
                acao="ask_sql",
            )
            llm_ms = round((time.monotonic() - inicio_llm) * 1000, 2)
        except ServicoIndisponivel as exc:
            llm_ms = round((time.monotonic() - inicio_llm) * 1000, 2)
            logger.warning(
                "acao=endpoint_ask_sql status=falha erro=servico_indisponivel "
                "duracao_ms=%s motivo=%s",
                llm_ms,
                exc.motivo,
            )
            raise ConsultaIndisponivel(exc.motivo) from exc
        except ErroProvedor as exc:
            llm_ms = round((time.monotonic() - inicio_llm) * 1000, 2)
            logger.warning(
                "acao=endpoint_ask_sql status=falha erro=provedor "
                "duracao_ms=%s http=%s",
                llm_ms,
                exc.status,
            )
            raise ProvedorIndisponivel(
                f"O provedor de LLM devolveu um erro (HTTP {exc.status})."
            ) from exc

        try:
            sql, params = extraction.extrair_sql(resultado["answer"])
            sql = safety.validar_sql(
                sql,
                config.ASK_SQL_MAX_ROWS,
                params,
            )
            inicio_exec = time.monotonic()
            dados_sql = execution.executar_sql(sql, params)
            exec_ms = round((time.monotonic() - inicio_exec) * 1000, 2)
        except ErroConsultaSQL as exc:
            logger.warning(
                "acao=endpoint_ask_sql status=falha erro=sql_invalido motivo=%s",
                str(exc)[:200],
            )
            raise SQLEntidadeInvalida(str(exc)) from exc

        logger.info(
            "acao=endpoint_ask_sql status=sucesso duracao_llm_ms=%.2f "
            "duracao_exec_ms=%.2f linhas=%s truncado=%s",
            llm_ms,
            exec_ms,
            dados_sql["row_count"],
            dados_sql["truncated"],
        )

        return Response(
            {
                "question": dados["question"],
                "sql": sql,
                "columns": dados_sql["columns"],
                "results": dados_sql["results"],
                "row_count": dados_sql["row_count"],
                "truncated": dados_sql["truncated"],
                "meta": {
                    "tokens_prompt": resultado["tokens_prompt"],
                    "tokens_output": resultado["tokens_output"],
                    "llm_ms": llm_ms,
                    "execution_ms": exec_ms,
                },
            }
        )
