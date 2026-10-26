# AGENTS.md

## Visão Geral
SynapseShop é um monorepo com múltiplos serviços (Django REST API principal em `api/v1/products/`, `users-service` FastAPI, `inventory` FastAPI) orquestrados via `docker-compose.yml`. O projeto segue a abordagem SpecDD com specs por aula em `specs/`.

## Entry Points Rápidos
| Componente | Local | Descrição |
|---|---|---|
| API Principal (Django DRF) | `api/v1/products/manage.py`, `api/v1/products/products/` | Catálogo, Pedidos, Cache Redis, Mensageria Kafka, Assistente IA |
| Users Service (FastAPI) | `users-service/main.py` | Autenticação/usuários com Alembic |
| Inventory Service (FastAPI) | `inventory/main.py` | Serviço de inventário |
| Root App | `app.py` | App simples de healthcheck (Aula 3) |
| Dashboard (Streamlit) | `dashboard/app.py`, `dashboard/db.py` | Painel analítico na porta 8501 |
| Orquestração | `docker-compose.yml`, `Dockerfile` | Stack completo |
| Comandos centralizados | `tasks.py` | `test`, `coverage`, `lint`, `check`, `up`, `down`, `clean` |

## Como Rodar (sem Docker - mais rápido)
```bash
# Na raiz
python tasks.py test      # Suite completa (223 testes, ~2s, SQLite in-memory)
python tasks.py coverage  # Com relatório HTML
python tasks.py lint      # ruff + spectral
python tasks.py check     # lint + testes
```

## Como Rodar (com Docker)
```bash
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

## Mapa por Domínio (API Django)
| Domínio | Caminho | Propósito |
|---|---|---|
| Catálogo | `api/v1/products/catalog/` | Categories, Items (CRUD) |
| Pedidos | `api/v1/products/orders/` | Orders, Cache Redis, Mensageria Kafka (produtor/consumidor/worker), métricas |
| Assistente IA | `api/v1/products/assist/` | `/api/v1/assist` - sumarização/explicação com LLM resiliente (retry/circuit breaker/redação PII) |
| Config/Core | `api/v1/products/products/` | settings, urls, middleware, exceptions, api_conventions, health, openapi |
| Testes | `api/v1/products/tests/` | unit/ e integration/ |

## Serviços Externos
| Serviço | Porta | Uso |
|---|---|---|
| PostgreSQL | 5432 | Banco principal (API) |
| Redis | 6379 | Cache-aside (pedidos) + dedupe/idempotência Kafka |
| Redpanda (Kafka) | 9094/9092 | Mensageria (pedidos.criado, pedidos.pagamento, DLQs) |

## Documentação Importante
| Arquivo | Quando usar |
|---|---|
| `README.md` | Documentação completa por aula (histórico detalhado) |
| `docs/INDEX.md` | Índice navegável (criado nesta otimização) |
| `docs/openapi.yaml` | Contrato OpenAPI 3.0.3 |
| `specs/` | Especificações por aula (SpecDD) |
| `postman/` | Coleção Postman para testes manuais |
| `CHANGELOG.md` | Histórico de mudanças |
| `docs/historico/PROMPTS.md` | Histórico de prompts IA (grande - prefira índices) |

## Dicas para Agentes (Otimizado)
- **Comece pelo índice**: Leia `docs/INDEX.md` antes de varrer o projeto inteiro
- **Use caminhos específicos**: Prefira `glob("api/v1/products/orders/**/*.py")` ao invés de ler toda a árvore
- **Evite ler arquivos gigantes**: `README.md` (52KB) e `docs/historico/PROMPTS.md` (27KB) são históricos - use índices
- **Comandos centralizados**: Sempre use `python tasks.py` ao invés de comandos ad hoc
- **Testes rápidos**: A suíte roda em SQLite in-memory sem Docker - ideal para validação
- **Specs primeiro**: Para entender "por que", consulte `specs/specs_da_aula_*.md` relevante
- **Sem ruído**: Ignore `.pytest_cache/`, `__pycache__/`, `.coverage` em buscas
