## Aula 12 — Testes automatizados e cobertura

### Objetivo

Suíte de testes unitários e de integração com `pytest` para a API Django
(`api/v1/products`), executada dentro do contêiner, com medição de cobertura
e *fakes* que isolam as dependências externas (Redis, Kafka, relógio). Escopo
restrito à API principal — sem OpenAPI/Swagger/Postman (Aula 13).

### Como executar os testes

Desde a **Onda 0** a suíte corre **sem Docker e sem Postgres**: por omissão usa
SQLite em memória (`products/settings_test.py`), porque os modelos do projeto só
usam campos padrão do Django. A suite completa leva ~2 segundos.

```bash
python tasks.py test                                  # tudo, com cobertura
python tasks.py coverage                              # + relatório HTML
cd api/v1/products && pytest tests/unit               # só unitários
cd api/v1/products && pytest tests/integration        # só integração
cd api/v1/products && pytest tests/unit/test_cache.py  # um módulo
cd api/v1/products && pytest -k pagamento -q          # por nome
```

Para validar contra o motor de produção (PostgreSQL) basta exportar
`DB_ENGINE=postgres` — a CI corre a suíte nos **dois** motores, numa matriz,
para garantir que nenhuma query depende de um deles:

```bash
DB_ENGINE=postgres POSTGRES_DB=synapseshop POSTGRES_USER=synapse \
  POSTGRES_PASSWORD=synapseshop DB_HOST=localhost pytest
```

Alternativa com contentores (a forma histórica, ainda válida):

```bash
docker compose build api
docker compose up -d api
docker compose exec api pytest                       # tudo, com cobertura
docker compose exec api pytest tests/unit            # só unitários
```

A cobertura é reportada no fim de cada execução (`--cov=assist --cov=orders
--cov=catalog --cov=products --cov-report=term-missing`, definido em
`api/v1/products/pytest.ini` junto com `DJANGO_SETTINGS_MODULE` e
`testpaths=tests`). As dependências estão pinadas em `requirements.txt`
(`pytest`, `pytest-django`, `pytest-cov`, `freezegun`).

### Estrutura da suíte

```
api/v1/products/
├── pytest.ini                 # settings do pytest + addopts de cobertura
├── products/
│   └── settings_test.py       # motor da BD de teste (SQLite por omissão)
└── tests/
    ├── conftest.py            # fixtures globais + DJANGO_ALLOW_ASYNC_UNSAFE
    ├── unit/                  # cache, contrato, idempotência, métricas,
    │                          # serializers, health, models, entrypoints,
    │                          # produtor, tópicos e os 2 workers Kafka
    └── integration/           # ciclo de vida dos endpoints (CRUD, pagar,
                               # métricas) contra BD efémera
```

A BD de teste é efémera: SQLite em memória por omissão, ou a base de testes
do Postgres (`test_<POSTGRES_DB>`) quando `DB_ENGINE=postgres`, criada e
destruída pelo `pytest-django` a cada execução.

### Convenções, fixtures e mocks

| Fixture / convenção | Onde | O que faz |
|---|---|---|
| `api_client` | `tests/conftest.py` | Cliente HTTP para os testes de integração |
| `cache_teste` (autouse) | `tests/conftest.py` | Cache locmem limpo entre testes |
| `relogio_fixo` | `tests/conftest.py` | Congela o tempo a `2026-01-15T12:00:00` |
| `publicador_falso` | `tests/conftest.py` | Substitui o produtor Kafka |
| `fabrica_pedido` | `tests/conftest.py` | Cria `Order` de teste |
| `sync_local` (autouse) | testes dos workers | Reduz `sync_to_async` a chamada direta, para o ORM ver a transação do teste |
| `sem_backoff` (autouse) | testes dos workers | Backoff instantâneo — nenhum teste dorme |

- Nome dos testes: `test_<comportamento>_<condição>_<resultado>`, com
  parametrização onde há cenários repetidos (caminhos felizes **e** de erro).
- Nada partilha estado entre testes: Redis de teste é isolado, o relógio é
  fixo e a BD é transacional por teste.
- O Kafka nunca é usado: os workers são testados com fakes
  (`FakeConsumidor`, `FakeProdutorDLQ`, `FakeProducer`) e falhas simuladas
  (`RedisIndisponivel`, `CacheCorrida`).
- Testes de integração validam o ciclo `POST` → `GET` → efeitos na base de
  dados e os *status codes* (201/200/400/402/404/409).

Nota técnica: `asyncio.run` cria a task com um *contextvar* storage próprio
(asgiref `Local` em modo async) que **não** herda a ligação BD guardada no
thread-local. Os helpers `_rodar` dos testes de workers copiam a ligação da
transação do teste para dentro da coroutine, e `tests/conftest.py` define
`DJANGO_ALLOW_ASYNC_UNSAFE=1` — sem isto o ORM dentro do *event loop* ou
abre uma ligação cega à transação ou levanta `SynchronousOnlyOperation`.

### Resultado e metas de cobertura

| Métrica | Meta | Obtido |
|---|---|---|
| Testes | — | **191** (unit + integração), todos verdes |
| Cobertura global | ≥ 85% | **98%** (925 instruções) |
| Utilitários críticos (`orders/cache.py`, `orders/mensageria/*`, `products/api_conventions.py`) | 100% | 100% |

A cobertura é apenas *reportada* (sem `--cov-fail-under`); o gate em CI e a
execução automatizada em GitHub Actions ficam para pendência registada.

### Escopo da Aula 12

Apenas a suíte de testes da API Django principal (`orders`, `catalog`,
`products`). **Não** foram antecipados: OpenAPI/Swagger/Postman (Aula 13),
testes de `users-service`/`inventory-service`, pipeline de CI/CD ou gate de
cobertura obrigatório.
