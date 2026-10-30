"""Contexto de schema injetado no prompt da LLM (Aula 21).

O contexto e derivado dos modelos Django (``Model._meta``), sem consultar o
catalogo do PostgreSQL. Isso mantem o mesmo comportamento em SQLite (testes) e
PostgreSQL (producao) e limita o que a LLM pode referenciar.

Apenas as tabelas de negocio geridas pelo Django sao expostas:

- ``orders_order``
- ``catalog_item``
- ``catalog_category``

As tabelas ``users``/``tokens`` pertencem ao ``users-service`` (Alembic) e
ficam de fora de proposito.
"""

from functools import lru_cache

TABELAS_PERMITIDAS = (
    "orders_order",
    "catalog_item",
    "catalog_category",
)

# Mecanismo de defesa para futuras tabelas: nenhuma coluna destas tabelas deve
# chegar ao prompt nem ao resultado.
COLUNAS_SENSIVEIS = frozenset(
    {
        "senha_hash",
        "password",
        "token",
        "api_key",
        "secret",
    }
)

_DESCRICOES = {
    "orders_order": "Pedidos realizados pelos utilizadores.",
    "catalog_item": "Itens/produtos do catalogo.",
    "catalog_category": "Categorias do catalogo.",
}


def _tipo_sql(campo):
    interno = campo.get_internal_type()
    if interno in ("AutoField", "BigAutoField", "BigIntegerField"):
        return "BIGINT"
    if interno in (
        "IntegerField",
        "SmallIntegerField",
        "PositiveIntegerField",
        "PositiveSmallIntegerField",
        "ForeignKey",
    ):
        return "INTEGER"
    if interno == "CharField":
        return f"VARCHAR({campo.max_length})"
    if interno == "DecimalField":
        return f"NUMERIC({campo.max_digits}, {campo.decimal_places})"
    if interno == "DateTimeField":
        return "TIMESTAMP"
    if interno == "DateField":
        return "DATE"
    if interno == "TimeField":
        return "TIME"
    if interno == "BooleanField":
        return "BOOLEAN"
    if interno == "FloatField":
        return "DOUBLE PRECISION"
    if interno == "JSONField":
        return "JSONB"
    if interno == "UUIDField":
        return "UUID"
    if interno == "TextField":
        return "TEXT"
    return "TEXT"


def _modelos_permitidos():
    from catalog.models import Category, Item
    from orders.models import Order

    return (Order, Item, Category)


def _colunas(modelo):
    partes = []
    for campo in modelo._meta.concrete_fields:
        if campo.name in COLUNAS_SENSIVEIS:
            continue

        tipo = _tipo_sql(campo)
        if campo.primary_key:
            restricao = " PRIMARY KEY"
        elif campo.null:
            restricao = " NULL"
        else:
            restricao = " NOT NULL"

        referencia = ""
        if campo.is_relation and campo.related_model is not None:
            tabela_alvo = campo.related_model._meta.db_table
            referencia = f" REFERENCES {tabela_alvo}({campo.target_field.column})"

        partes.append(
            f"  {campo.column} {tipo}{restricao}{referencia}"
        )
    return partes


@lru_cache(maxsize=1)
def construir_schema_ddl():
    """Devolve o DDL textual usado no prompt (deterministico e cacheado)."""
    blocos = []
    for modelo in _modelos_permitidos():
        tabela = modelo._meta.db_table
        if tabela not in TABELAS_PERMITIDAS:
            continue
        descricao = _DESCRICOES.get(tabela, "")
        corpo = ",\n".join(_colunas(modelo))
        blocos.append(
            f"-- {tabela}: {descricao}\n"
            f"CREATE TABLE {tabela} (\n{corpo}\n);"
        )
    return "\n\n".join(blocos)
