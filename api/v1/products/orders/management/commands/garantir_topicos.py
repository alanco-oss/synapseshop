"""Garante a criacao/configuracao dos topicos Kafka (Aula 10).

Executado no arranque do worker (e disponivel como comando avulso)::

    python manage.py garantir_topicos
"""
from django.core.management.base import BaseCommand

from orders.mensageria import topicos


class Command(BaseCommand):
    help = "Cria/ajusta os topicos Kafka (pedidos.criado e pedidos.criado.dlq)"

    def handle(self, *args, **options):
        topicos.garantir_sync()