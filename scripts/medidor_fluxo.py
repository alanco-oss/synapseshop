"""Benchmark de latencia e throughput do fluxo ``PedidoCriado`` (Aula 10).

Mede, numa so execucao, o custo de cada etapa:

- **produtor**: pedidos criados pelo ``POST /api/v1/pedidos/`` com concorrencia
  (threads) — latencia por pedido (media/p95) e vazao (RPS);
- **consumidor**: espera ativa o contador do endpoint de metricas chegar aos
  ``N`` pedidos publicados — vazao de consumo (eventos/s) e tempo ponta-a-ponta
  medio (publicacao -> processamento), via deltas dos contadores Redis.

Resultado: tabelas no README da Aula 10 (como o ``medir_cache.py`` faz para o
cache). Apos a execucao, os acumulados do Redis continuam disponiveis em
``/api/v1/pedidos/metricas-mensageria/``.

Uso (a partir da raiz, com a stack em ``docker compose up``)::

    api/v1/products/.venv/Scripts/python scripts/medidor_fluxo.py --pedidos 200
"""
import argparse
import json
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROTA_PEDIDOS = "/api/v1/pedidos/"
ROTA_METRICAS = "/api/v1/pedidos/metricas-mensageria/"


def _requisicao(endereco, payload=None):
    dados = json.dumps(payload).encode("utf-8") if payload is not None else None
    pedido = urllib.request.Request(
        endereco, data=dados, headers={"Content-Type": "application/json"}
    )
    inicio = time.perf_counter()
    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        resposta.read()
    return (time.perf_counter() - inicio) * 1000


def _metricas(endereco):
    with urllib.request.urlopen(endereco + ROTA_METRICAS, timeout=10) as resposta:
        return json.load(resposta)


def _percentil(valores, fracao):
    ordenados = sorted(valores)
    indice = min(len(ordenados) - 1, int(len(ordenados) * fracao))
    return ordenados[indice]


def fase_produtor(endereco, pedidos, concorrencia):
    payload = {"user_id": 10, "total": "19.90"}

    def publicar(_):
        return _requisicao(endereco + ROTA_PEDIDOS, payload)

    inicio = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concorrencia) as executor:
        latencias = list(executor.map(publicar, range(pedidos)))
    duracao = time.perf_counter() - inicio
    return {
        "publicacoes": len(latencias),
        "media_ms": statistics.mean(latencias),
        "p95_ms": _percentil(latencias, 0.95),
        "rps": len(latencias) / duracao,
        "duracao_s": duracao,
    }


def fase_consumidor(endereco, esperados, timeout, antes=None):
    if antes is None:
        antes = _metricas(endereco)["consumidor"]
    inicio = time.perf_counter()
    alvo = antes["consumos"] + esperados
    ultimas = antes
    while time.perf_counter() - inicio < timeout:
        ultimas = _metricas(endereco)["consumidor"]
        if ultimas["consumos"] >= alvo:
            break
        time.sleep(0.2)
    detectado = time.perf_counter()
    consumidos = ultimas["consumos"] - antes["consumos"]
    latencia_total = ultimas["latencia_total_ms"] - antes["latencia_total_ms"]
    duracao_total = ultimas["duracao_total_ms"] - antes["duracao_total_ms"]
    consumidor = (
        ultimas["consumos"],
        consumidos,
        latencia_total,
        duracao_total,
    )
    return consumidor, inicio, detectado


def main():
    parser = argparse.ArgumentParser(
        description="Mede latencia e throughput do fluxo PedidoCriado."
    )
    parser.add_argument("--endereco", default="http://127.0.0.1:8000")
    parser.add_argument("--pedidos", type=int, default=200)
    parser.add_argument("--concorrencia", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=60, help="aguarda o consumo")
    args = parser.parse_args()

    inicio_global = time.perf_counter()
    antes = _metricas(args.endereco)["consumidor"]
    produtor = fase_produtor(args.endereco, args.pedidos, args.concorrencia)
    consumido, inicio_consumo, detectado = fase_consumidor(
        args.endereco, args.pedidos, args.timeout, antes
    )
    total_consumos, consumidos, latencia_total, duracao_total = consumido
    rps_consumo = (
        consumidos / (detectado - inicio_global) if detectado > inicio_global else 0.0
    )

    print(
        f"produtor: {produtor['publicacoes']} pedidos em {produtor['duracao_s']:.2f}s "
        f"media={produtor['media_ms']:.2f}ms p95={produtor['p95_ms']:.2f}ms "
        f"rps={produtor['rps']:.1f}"
    )
    print(
        f"consumidor: {consumidos} eventos totais={total_consumos} em "
        f"{detectado - inicio_global:.2f}s "
        f"latencia_media={latencia_total / consumidos:.2f}ms "
        f"duracao_media={duracao_total / consumidos:.2f}ms "
        f"rps={rps_consumo:.1f}"
    )

    print()
    print("| etapa | requisicoes | duracao_s | media_ms | p95_ms | rps |")
    print("| --- | --- | --- | --- | --- | --- |")
    print(
        f"| produtor (POST /pedidos) | {produtor['publicacoes']} | "
        f"{produtor['duracao_s']:.2f} | {produtor['media_ms']:.2f} | "
        f"{produtor['p95_ms']:.2f} | {produtor['rps']:.1f} |"
    )
    print(
        f"| consumidor (worker) | {consumidos} | "
        f"{detectado - inicio_consumo:.2f} | {duracao_total / consumidos:.2f} | - | "
        f"{rps_consumo:.1f} |"
    )
    return 0 if consumidos == args.pedidos else 1


if __name__ == "__main__":
    sys.exit(main())