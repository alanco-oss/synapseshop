# Changelog

Todas as alterações relevantes do SynapseShop. O formato segue
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota
versionamento por rota (`/api/v1/`).

## [Aula 14] — Assistente de IA com `llm_service` resiliente

### Adicionado
- App `assist` (`api/v1/products/assist/`) com `POST /api/v1/assist`
  (`summarize`/`explain`) — aceita também a forma com barra final.
- `llm_service` com timeout ≤ 5 s, 3 tentativas de retry com *backoff*
  exponencial + *jitter* e circuit breaker (aberto → meio-aberto → fechado).
- `redaction.py` — redação de PII (emails, CPF/CNPJ, cartões, telefones, IPs,
  `Bearer`, linha de senhas/segredos) antes do envio e nos logs.
- Telemetria em logs estruturados com duração, tentativas, HTTP status e custo
  estimado (com pedido/prompt sempre redigidos).
- Testes: `test_redaction.py`, `test_prompts.py`, `test_llm_service.py` e
  `test_assist_endpoint.py` (32 testes; suíte completa 223 verdes, 98%).
- `specs/issues_da_aula_14.md` — pendências extra-spec registadas.

### Alterado
- `products/settings.py`/`urls.py`: registo do app e das rotas `assist`.
- `products/exceptions.py`: `TITULOS` ganhou `502` (gateway inválido) e `503`
  (serviço indisponível) para o envelope RFC 7807.
- `requirements.txt` (`requests==2.32.5`), `pytest.ini`
  (`--cov=assist`) e `docker-compose.yml` (envs `LLM_*` no serviço `api`).
- `README.md` (capítulo Aula 14), `PROMPTS.md` (histórico) e `CHANGELOG.md`.
- `docs/openapi.yaml`: tag `Assistente`, path `/api/v1/assist/`, respostas
  `GatewayInvalido`/`AssistenteIndisponivel` e schemas `AssistEntrada`,
  `AssistResposta`, `AssistMeta`; lint Spectral sem erros.
- Coleção Postman com a pasta `Assistente` (casos 200/400/503).

### Escopo
- Assistente de logs resiliente, com testes *offline* (provedor fake). Sem
  métricas de Redis para o circuito, cache de respostas, guardrails, testes de
  integração, streaming, rotação segura de chave ou autenticação do endpoint.

## [Aula 13] — Documentação OpenAPI/Swagger e Postman/Insomnia

### Adicionado
- `docs/openapi.yaml` — contrato completo (tags, exemplos de pedido/resposta,
  `ErrorSchema`/RFC 7807, paginação, filtros, ordenação e cabeçalhos).
- Interfaces interativas **Swagger UI** (`/api/v1/docs/`) e **ReDoc**
  (`/api/v1/redoc/`), com o schema em `/api/v1/schema/`.
- `postman/environments/SynapseShop Local.postman_environment.json` e casos de
  sucesso/erro na coleção Postman.
- `docs/checklist_integrador_externo.md` — URLs, autenticação, *rate limits* e
  política de versionamento.
- `.spectral.yaml` — regras de lint do contrato OpenAPI.

### Alterado
- `README.md` com o capítulo da Aula 13.
- `PROMPTS.md` com o histórico de IA da Aula 13.
- Convenções da API em `products/api_conventions.py` (paginação opcional por
  `page`/`limit`, filtros e ordenação `sort=campo:asc|desc`).
- Tratamento de erros padronizado (RFC 7807) em `products/exceptions.py`.
- Cabeçalho de correlação `X-Trace-Id` via `products/middleware.py`.

### Escopo
- Documentação e padronização da API existente. Sem IA, mensageria avançada ou
  dashboards analíticos (aulas posteriores).

## [Aula 12] — Testes automatizados e cobertura

### Adicionado
- Suíte `pytest` em `api/v1/products/tests/` (`unit/` e `integration/`), com
  `conftest.py`, *fakes* de Redis/Kafka e relógio fixo.
- `pytest.ini` com `--cov=orders --cov=catalog --cov=products`.
- Dependências de teste pinadas em `requirements.txt` (`pytest`,
  `pytest-django`, `pytest-cov`, `freezegun`).

### Resultado
- 173 testes verdes, cobertura global de 99% (utilitários críticos a 100%).

## [Aula 11] — Núcleo do mini-backend

### Adicionado
- Endpoint `POST /api/v1/pedidos/{id}/pagar/` (200/402/409/400).
- Worker `consumir_pagamento` (notificação simulada) e tópico `pedidos.pagamento`.
- `GET /health` no Django com estado de `db`, `redis` e `kafka`.

## [Aula 10] — Kafka: partições, offsets, streams e métricas

### Adicionado
- Métricas de latência/throughput (`/api/v1/pedidos/metricas-mensageria/`).
- Scripts `scripts/estatisticas_stream.py`, `medidor_fluxo.py` e
  `simular_duplicado.py`.

## [Aula 9] — Mensageria assíncrona com Kafka

### Adicionado
- Produtor, consumidor `consumir_pedido_criado`, contrato `PedidoCriado`,
  idempotência em Redis e DLQ.

## [Aula 8] — Cache-aside com Redis

### Adicionado
- Cache-aside em `/api/v1/pedidos/` e `/detalhes/`, invalidação por evento,
  métricas de *hit rate* e degradação graciosa.

## [Aula 7] — (ver README)

## [Aula 6] — PostgreSQL e migrações

## [Aula 5] — (ver README)

## [Aula 4] — CRUD com Django REST Framework

### Adicionado
- App `catalog` (`Category`, `Item`), rotas `/api/v1/categories/` e
  `/api/v1/items/`, coleção Postman e checklist IA-safe.

## [Aula 3] — Docker essencial

### Adicionado
- `Dockerfile` multistage, `docker-compose.yml` (API + PostgreSQL) e
  `GET /health`.
