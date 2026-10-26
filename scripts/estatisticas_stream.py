"""Leitura independente do stream ``PedidoCriado`` (Aula 10).

Demonstra que o topico e um *log* continuo: um segundo consumidor (grupo
distinto, ``auto_offset_reset=earliest``) le o stream do inicio — sem afetar o
progresso dos workers — e agrega contagens por particao, total de eventos e
latencias (ocorrencia -> consumo), ilustrando o processamento de streams sem
Kafka Streams/Java.

Uso (na maquina local, a partir da raiz)::

    api/v1/products/.venv/Scripts/python scripts/estatisticas_stream.py --limite 50
    api/v1/products/.venv/Scripts/python scripts/estatisticas_stream.py --duracao 5
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from aiokafka import AIOKafkaConsumer

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "api" / "v1" / "products"))

from orders.mensageria import topicos  # noqa: E402

GRUPO_LEITURA = "synapseshop-estatisticas-stream"


def _latencia(evento):
    ocorrido = datetime.fromisoformat(evento["occurred_at"])
    return (datetime.now(UTC) - ocorrido).total_seconds() * 1000


async def colecionar(bootstrap, limite, duracao):
    consumidor = AIOKafkaConsumer(
        topicos.TOPICO_PEDIDO_CRIADO,
        bootstrap_servers=bootstrap,
        group_id=GRUPO_LEITURA,
        auto_offset_reset="earliest",
    )
    await consumidor.start()
    inicio = time.perf_counter()
    contagem = Counter()
    latencias = []
    lidas = 0
    try:
        async for mensagem in consumidor:
            contagem[f"particao_{mensagem.partition}"] += 1
            lidas += 1
            try:
                evento = json.loads(mensagem.value)
                latencias.append(_latencia(evento))
            except Exception:
                pass
            if limite and lidas >= limite:
                break
            if duracao and (time.perf_counter() - inicio) >= duracao:
                break
    finally:
        await consumidor.stop()

    def _estatistica(numeros):
        if not numeros:
            return {"contagem": 0}
        ordenados = sorted(numeros)
        p95 = ordenados[min(len(ordenados) - 1, int(len(ordenados) * 0.95))]
        return {
            "contagem": len(numeros),
            "min_ms": round(min(numeros), 2),
            "media_ms": round(statistics.mean(numeros), 2),
            "p95_ms": round(p95, 2),
            "max_ms": round(max(numeros), 2),
        }

    return {
        "topico": topicos.TOPICO_PEDIDO_CRIADO,
        "lidos": lidas,
        "por_particao": dict(contagem),
        "latencia": _estatistica(latencias),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Le o stream PedidoCriado do inicio e agrega estatisticas."
    )
    parser.add_argument("--bootstrap", default="localhost:9094")
    parser.add_argument("--limite", type=int, default=0, help="max. de eventos a ler")
    parser.add_argument("--duracao", type=float, default=0, help="janela em segundos")
    args = parser.parse_args()
    if not args.limite and not args.duracao:
        print("indique --limite ou --duracao")
        return 1

    resumo = asyncio.run(
        colecionar(args.bootstrap, args.limite or None, args.duracao or None)
    )
    print(
        f"topico={resumo['topico']} lidos={resumo['lidos']} "
        f"por_particao={resumo['por_particao']}"
    )
    lat = resumo["latencia"]
    if lat["contagem"]:
        print(
            "latencia_ms "
            f"min={lat['min_ms']} media={lat['media_ms']} "
            f"p95={lat['p95_ms']} max={lat['max_ms']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
