"""Re-publica um evento ``PedidoCriado`` ja existente (Aula 9).

Valida a idempotencia de ponta a ponta: publica de novo o evento de um pedido
processado, com a mesma chave de negocio ``pedido:{id}``, e o worker deve
registar ``dedupe=duplicada`` sem voltar a persistir.

Uso (dentro do contentor do API, com as env de DB/Kafka do compose)::

    docker compose exec -w /app/api/v1/products api \
        python /app/scripts/simular_duplicado.py --pedido-id 1
"""
import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "api" / "v1" / "products"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "products.settings")

import django  # noqa: E402

django.setup()

from orders.mensageria import contrato, produtor  # noqa: E402
from orders.models import Order  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Re-publica o evento PedidoCriado de um pedido (teste de duplicado)."
    )
    parser.add_argument("--pedido-id", type=int, required=True)
    args = parser.parse_args()

    try:
        pedido = Order.objects.get(pk=args.pedido_id)
    except Order.DoesNotExist:
        print(f"pedido {args.pedido_id} nao existe")
        return 1

    evento = contrato.construir_pedido_criado(pedido)
    sucesso = produtor.publicar_evento(evento)
    produtor.fechar()
    print(
        f"publicado={sucesso} pedido_id={pedido.pk} "
        f"chave_idempotencia={evento['idempotency_key']} event_id={evento['event_id']}"
    )
    return 0 if sucesso else 1


if __name__ == "__main__":
    sys.exit(main())
