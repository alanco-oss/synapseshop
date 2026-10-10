"""Telemetria do assistente (Aula 14).

Logs estruturados (formato ``key=value``, alinhado com ``orders.mensageria``)
com a latência, a taxa de erro (derivável do ``status=``), o consumo de tokens
e uma **estimativa de custo por chamada** calculada a partir dos preços
configurados (USD por 1M de tokens). Nenhum conteúdo bruto é registado — o
service só recebe os logs já redigidos.
"""
import logging

from . import config

logger = logging.getLogger("assist")


def estimar_custo(tokens_prompt, tokens_output):
    """Estimativa de custo em USD da chamada (modelo-independente)."""
    if not tokens_prompt and not tokens_output:
        return 0.0
    custo = (
        tokens_prompt / 1_000_000 * config.LLM_PRECO_INPUT_1M
        + tokens_output / 1_000_000 * config.LLM_PRECO_OUTPUT_1M
    )
    return round(custo, 6)


def registrar_chamada(
    tentativa,
    tentativas,
    status,
    duracao_ms=None,
    erro=None,
    tokens_prompt=None,
    tokens_output=None,
):
    """Regista uma tentativa de chamada ao provedor num log estruturado."""
    campos = f"acao=assistir status={status} tentativa={tentativa}/{tentativas}"
    if duracao_ms is not None:
        campos += f" duracao_ms={duracao_ms}"
    if erro is not None:
        campos += f" erro={erro}"
    if tokens_prompt is not None:
        custo = estimar_custo(tokens_prompt, tokens_output)
        campos += (
            f" tokens_prompt={tokens_prompt} tokens_output={tokens_output}"
            f" custo_usd={custo}"
        )
    if status == "sucesso":
        logger.info(campos)
    else:
        logger.warning(campos)