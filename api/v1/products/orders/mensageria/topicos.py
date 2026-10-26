"""Definicao e garantia dos topicos Kafka dos fluxos ``PedidoCriado`` (Aula 10)
e ``PagamentoSimulado`` (Aula 11).

Nomes, numero de particoes e retencao sao centralizados aqui (fonte unica,
usada pelo produtor, pelo worker e pelos scripts). `garantir` cria/ajusta os
topicos no arranque do worker:

- ``pedidos.criado``: ``KAFKA_PARTICOES`` particoes (paralelismo de consumo
  com varios workers no mesmo grupo), retencao curta (Kafka como fila
  operacional);
- ``pedidos.criado.dlq``: 1 particao e retencao longa (mensagens esgotadas
  destinam-se a inspecao/reprocessamento manual);
- ``pedidos.pagamento`` / ``pedidos.pagamento.dlq``: mesmo esquema para o
  evento ``PagamentoSimulado`` e a notificacao (Aula 11).

Se um topico ja existir, `garantir` aumenta o numero de particoes quando
faltam (nunca reduz, Kafka nao permite) e apenas informa sobre a retencao.
"""
import asyncio
import logging
import os

from aiokafka.admin import AIOKafkaAdminClient, NewPartitions, NewTopic

logger = logging.getLogger("orders.mensageria")

TOPICO_PEDIDO_CRIADO = "pedidos.criado"
TOPICO_DLQ = "pedidos.criado.dlq"
# Aula 11: fluxo de pagamento simulado e a sua notificacao
TOPICO_PAGAMENTO = "pedidos.pagamento"
TOPICO_PAGAMENTO_DLQ = "pedidos.pagamento.dlq"

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9094")
PARTICOES = int(os.getenv("KAFKA_PARTICOES", "3"))
RETENCAO_HORAS = int(os.getenv("KAFKA_RETENCAO_HORAS", "1"))
RETENCAO_DLQ_HORAS = int(os.getenv("KAFKA_RETENCAO_DLQ_HORAS", "168"))
TIMEOUT_LIGACAO = float(os.getenv("KAFKA_TIMEOUT_LIGACAO", "5"))

ESPECIFICACOES = {
    TOPICO_PEDIDO_CRIADO: {
        "particoes": PARTICOES,
        "retencao_ms": RETENCAO_HORAS * 3600 * 1000,
    },
    TOPICO_DLQ: {
        "particoes": 1,
        "retencao_ms": RETENCAO_DLQ_HORAS * 3600 * 1000,
    },
    TOPICO_PAGAMENTO: {
        "particoes": PARTICOES,
        "retencao_ms": RETENCAO_HORAS * 3600 * 1000,
    },
    TOPICO_PAGAMENTO_DLQ: {
        "particoes": 1,
        "retencao_ms": RETENCAO_DLQ_HORAS * 3600 * 1000,
    },
}


async def garantir():
    """Cria ou ajusta os topicos conforme `ESPECIFICACOES`; loga o resultado."""
    cliente = AIOKafkaAdminClient(bootstrap_servers=BOOTSTRAP_SERVERS)
    try:
        await cliente.start()
        existentes = await cliente.list_topics()
        detalhe = await cliente.describe_topics(list(existentes)) if existentes else {}
        for nome, cfg in ESPECIFICACOES.items():
            if nome not in existentes:
                await cliente.create_topics(
                    [
                        NewTopic(
                            name=nome,
                            num_partitions=cfg["particoes"],
                            replication_factor=1,
                            topic_configs={
                                "retention.ms": str(cfg["retencao_ms"]),
                                "cleanup.policy": "delete",
                            },
                        )
                    ]
                )
                logger.info(
                    "topico=%s acao=criado particoes=%d retencao_ms=%d",
                    nome,
                    cfg["particoes"],
                    cfg["retencao_ms"],
                )
                continue

            descricao = None
            for item in detalhe:
                nome_item = item.get("topic") if isinstance(item, dict) else item.topic
                if nome_item == nome:
                    descricao = item
                    break
            actuais = len(_particoes(descricao)) if descricao else 0
            if actuais < cfg["particoes"]:
                await cliente.create_partitions(
                    {nome: NewPartitions(total_count=cfg["particoes"])}
                )
                logger.info(
                    "topico=%s acao=particoes_aumentadas de=%d para=%d",
                    nome,
                    actuais,
                    cfg["particoes"],
                )
            else:
                logger.info(
                    "topico=%s acao=valido particoes=%d retencao_ms=%d",
                    nome,
                    actuais,
                    cfg["retencao_ms"],
                )
    finally:
        try:
            await cliente.close()
        except Exception:
            pass


def _particoes(descricao):
    """``describe_topics`` devolve dict ou objeto conforme a versao do aiokafka."""
    return descricao["partitions"] if isinstance(descricao, dict) else descricao.partitions


def garantir_sync():
    """Variante sincrona para ambientes sem asyncio ja em curso."""
    asyncio.run(garantir_com_retry())


async def garantir_com_retry():
    atraso = 1.0
    while True:
        try:
            await garantir()
            return
        except Exception as erro:
            logger.warning(
                "kafka=indisponivel acao=garantir_topicos erro=%s repetir_em=%.1fs",
                f"{type(erro).__name__}: {erro}" if str(erro) else type(erro).__name__,
                atraso,
            )
            await asyncio.sleep(atraso)
            atraso = min(atraso * 2, 10)
