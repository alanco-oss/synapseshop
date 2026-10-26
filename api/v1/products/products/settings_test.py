# ruff: noqa: F403
"""Settings de teste (Aula 12, alargado na Onda 0 de otimizacao).

Motivo: a suite tem de correr **sem Docker e sem Postgres instalados**. Por
omissao usa SQLite em memoria, que e suficiente para os modelos do projeto
(``Order`` e ``Category``/``Item`` so usam campos padrao do Django, sem tipos
exclusivos do PostgreSQL).

Para validar contra o motor de producao basta exportar a variavel de ambiente
``DB_ENGINE=postgres`` (e as credenciais) — a CI corre a suite nos dois motores
para garantir que nenhuma query depende de um deles.

    DB_ENGINE=postgres pytest
"""
import os

from .settings import *  # noqa: F401

MOTOR = os.getenv("DB_ENGINE", "sqlite").strip().lower()

if MOTOR != "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

# O cache de teste ja e substituido pela fixture ``cache_teste`` (locmem);
# aqui so garantimos que nenhum teste depende do Redis real.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "synapseshop-testes",
    }
}

# Sem este flag o Django recusa queries no contexto async dos workers.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

# Hashes deterministicos para os testes de password.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
