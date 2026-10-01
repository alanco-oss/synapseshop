"""Medicao de desempenho do cache-aside dos pedidos (Aula 8).

Compara tres fases para o mesmo recurso, usando apenas a biblioteca padrao:

- ``sem_cache``  caminho de dados de antes do cache existir: consulta ao ORM
  seguida da serializacao, sem passar pelo cache nem pelo HTTP;
- ``cache_miss``  endpoint real com o Redis ativo e a chave removida antes de
  cada requisicao (lookup + banco + preenchimento);
- ``cache_hit``   endpoint real com a chave ja aquecida (caminho quente).

A fase ``cache_miss`` roda com concorrencia 1 de proposito: em paralelo uma
thread pode aquecer a chave antes da consulta da outra, o que contaminaria a
medicao do caminho frio. As requisicoes das fases de endpoint passam pelo WSGI
do Django em processo (sem socket), de modo que a diferenca mede o ganho do
cache e nao a latencia de rede.

Uso, a partir da raiz do projeto::

    api/v1/products/.venv/Scripts/python scripts/medir_cache.py --seed 500
"""
import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "api" / "v1" / "products"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "products.settings")

import django  # noqa: E402

django.setup()

from django.core.cache import cache  # noqa: E402
from django.db import connection, connections  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from orders import cache as cache_pedidos  # noqa: E402
from orders.models import Order  # noqa: E402
from orders.serializers import OrderSerializer  # noqa: E402

ROTAS = {
    "lista": "/api/v1/pedidos/",
    "detalhes": "/api/v1/pedidos/{id}/detalhes/",
}


def semear(minimo):
    total_atual = Order.objects.count()
    if total_atual >= minimo:
        return total_atual
    Order.objects.bulk_create(
        [
            Order(
                user_id=1 + indice % 10,
                status="pending",
                total=Decimal("19.90") * (1 + indice % 20),
            )
            for indice in range(total_atual, minimo)
        ]
    )
    return Order.objects.count()


def chave_do_endpoint(endpoint, pedido_id):
    if endpoint == "lista":
        return cache_pedidos.chave_lista()
    return cache_pedidos.chave_detalhes(pedido_id)


def percentil(latencias, fracao):
    ordenadas = sorted(latencias)
    indice = min(len(ordenadas) - 1, int(len(ordenadas) * fracao))
    return ordenadas[indice]


def em_paralelo(criar_acao, repeticoes, concorrencia):
    """Cada thread repete a acao criada para ela e registra as latencias em ms."""
    latencias = []

    def worker():
        acao = criar_acao()
        for _ in range(repeticoes):
            inicio = time.perf_counter()
            acao()
            latencias.append((time.perf_counter() - inicio) * 1000)
        connections.close_all()

    with ThreadPoolExecutor(max_workers=concorrencia) as executor:
        list(executor.map(lambda indice: worker(), range(concorrencia)))
    return latencias


def fase_orm(repeticoes, concorrencia, muitos, pedido_id):
    """Consulta + serializacao diretas, sem cache e sem HTTP."""
    if muitos:
        def criar_acao():
            return lambda: OrderSerializer(Order.objects.all(), many=True).data
    else:
        def criar_acao():
            return lambda: OrderSerializer(
                Order.objects.filter(pk=pedido_id).first()
            ).data

    return em_paralelo(criar_acao, repeticoes, concorrencia)


def fase_http(rota, chave, repeticoes, concorrencia, apagar_antes):
    """Chamadas reais ao endpoint; apagar_antes forca um miss por requisicao."""
    def criar_acao():
        cliente = APIClient()

        def acao():
            if apagar_antes:
                cache.delete(chave)
            resposta = cliente.get(rota)
            if resposta.status_code != 200:
                raise RuntimeError(f"{rota} respondeu {resposta.status_code}")

        return acao

    return em_paralelo(criar_acao, repeticoes, concorrencia)


def cronometrar(nome, descricao, execucao, concorrencia):
    inicio = time.perf_counter()
    latencias = execucao()
    duracao = time.perf_counter() - inicio
    print(f"  {nome}: {len(latencias)} requisicoes em {duracao:.2f}s")
    return (
        f"| {nome} | {descricao} | {concorrencia} | {len(latencias)} | "
        f"{sum(latencias) / len(latencias):.2f} | "
        f"{percentil(latencias, 0.95):.2f} | "
        f"{len(latencias) / duracao:.1f} |"
    )


def main():
    parser = argparse.ArgumentParser(description="Mede o ganho do cache-aside.")
    parser.add_argument("--endpoint", choices=sorted(ROTAS), default="lista")
    parser.add_argument("--id", type=int, default=1, help="pedido usado no /detalhes")
    parser.add_argument("--requisicoes", type=int, default=300)
    parser.add_argument(
        "--requisicoes-miss",
        type=int,
        default=30,
        help="amostra do caminho frio, que e sequencial e bem mais cara",
    )
    parser.add_argument("--concorrencia", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0, help="minimo de pedidos na base")
    parser.add_argument(
        "--verbose", action="store_true", help="mantem o log de hit/miss por requisicao"
    )
    args = parser.parse_args()

    logging.getLogger("orders.cache").setLevel(
        logging.INFO if args.verbose else logging.ERROR
    )

    if args.seed:
        print(f"pedidos na base: {semear(args.seed)}")

    rota = ROTAS[args.endpoint].format(id=args.id)
    chave = chave_do_endpoint(args.endpoint, args.id)
    repeticoes = (
        args.requisicoes - (args.requisicoes % args.concorrencia)
    ) // args.concorrencia

    print(f"endpoint={rota}")

    def aquecer():
        if APIClient().get(rota).status_code != 200:
            raise RuntimeError(f"nao foi possivel aquecer {rota}")

    linhas = [
        cronometrar(
            "sem_cache",
            "ORM + serializer, sem cache nem HTTP",
            lambda: fase_orm(
                args.requisicoes_miss, 1, args.endpoint == "lista", args.id
            ),
            1,
        ),
        cronometrar(
            "cache_miss",
            "endpoint com a chave apagada",
            lambda: fase_http(rota, chave, args.requisicoes_miss, 1, apagar_antes=True),
            1,
        ),
    ]

    aquecer()
    linhas.append(
        cronometrar(
            "cache_hit",
            "endpoint com a chave aquecida",
            lambda: fase_http(rota, chave, args.requisicoes_miss, 1, apagar_antes=False),
            1,
        )
    )

    aquecer()
    linhas.append(
        cronometrar(
            "cache_hit_carga",
            "endpoint com a chave aquecida sob concorrencia",
            lambda: fase_http(
                rota, chave, repeticoes, args.concorrencia, apagar_antes=False
            ),
            args.concorrencia,
        )
    )

    connection.close()
    print()
    print("| fase | cenario | concorrencia | requisicoes | media_ms | p95_ms | rps |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    print("\n".join(linhas))


if __name__ == "__main__":
    main()