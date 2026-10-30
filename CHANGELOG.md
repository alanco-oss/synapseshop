# Changelog

Todas as alterações relevantes do SynapseShop. O formato segue
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota
versionamento por rota (`/api/v1/`).

## [Aula 22] — Pipeline de CI/CD com GitHub Actions

### Adicionado
- Badge de status da CI no topo do `README.md` e secção "Aula 22" com gatilhos,
  jobs, reprodução local e configuração de segredos.
- `docs/aulas/AULA_22.md` — arquitetura do pipeline, matriz SQLite/PostgreSQL,
  *troubleshooting* e checklist do DoD.
- Suporte a `SECRET_KEY` por variável de ambiente em
  `api/v1/products/products/settings.py`, mantendo a chave de desenvolvimento
  como *fallback*.

### Alterado
- `.github/workflows/ci.yml` — reorganizado nos jobs `test-and-lint` (matriz
  SQLite/PostgreSQL, ruff, Spectral, *gate* de cobertura de 95%) e
  `docker-build` (`docker compose config` e build de `synapseshop-api:test` e
  `synapseshop-inventory:test`), com `needs` para o build só correr após os
  testes. Adicionados `permissions: contents: read` e `concurrency`.
- `README.md` — lista de documentação por aula passa a incluir a Aula 22.
- `specs/README.md` — índice atualizado com as Aulas 19 a 22.
- `PROMPTS.md` e `docs/historico/PROMPTS.md` — registo dos prompts e decisões
  da Aula 22.

### Sem impacto no exterior
- Contrato HTTP `/api/v1/*` e `docs/openapi.yaml` inalterados.
- Nenhum segredo é versionado; `.env` continua ignorado pelo Git.

## [Otimização — Onda 0] — Rede de segurança: CI, lint e testes sem Docker

### Adicionado
- `.github/workflows/ci.yml` — pipeline com três *jobs*: `testes` (matriz
  SQLite + PostgreSQL, gate de cobertura), `lint` (ruff + Spectral) e `build`
  (as duas imagens Docker). Dispara em *push* e *pull request* para
  `master`/`main`.
- `api/v1/products/products/settings_test.py` — settings de teste com SQLite em
  memória; a suíte passou a correr **sem Docker, Postgres, Redis ou Kafka**
  (de ~19 s com erros de ligação para ~2 s com 223 testes verdes).
- `ruff.toml` e `.editorconfig` — convenções de lint e de edição partilhadas.
- `tasks.py` — comandos de operação em Python puro (`test`, `coverage`,
  `lint`, `check`, `up`, `down`, `build`, `clean`), funcionam em Windows,
  Linux e macOS sem instalar nada.
- `.gitattributes` — finais de linha normalizados em LF em todo o repositório
  (elimina o aviso `LF will be replaced by CRLF` e o ruído entre SO).
- Secção "Comandos de operação" no topo do `README.md`.

### Corrigido
- `tests/unit/test_produtor.py` — o fake `LoopFalso` não era um event loop
  válido, e `asyncio.set_event_loop` estourava dentro da thread
  `kafka-produtor-loop`, deixando uma exceção não tratada a cada execução.
  Agora o fake herda de `asyncio.AbstractEventLoop`.
- `products/openapi.py` — a substituição do URL do esquema usava `%`-formatting;
  passou a `str.replace` (o template tem JavaScript com `{}` que colidiria com
  f-strings e `.format`).
- `assist/views.py`, `users-service/dependencies.py` e
  `users-service/routers/auth_router.py` — reencaminhamento de exceções sem
  `from erro` (encadeamento perdido no traceback).
- `users-service/alembic/env.py` — variável `url` morta (o código usava
  `DATABASE_URL`); imports duplicados.
- `users-service/models/token.py` — `Index` importado duas vezes.
- `.gitignore` — `.postman/` ignorava a pasta que contém
  `resources.yaml`, a ligação ao workspace partilhado (que tem de estar no
  controlo de versões).

### Alterado
- `api/v1/products/pytest.ini` — aponta para `products.settings_test`;
  `--strict-markers` e `--strict-config`; as exceções não tratadas em threads
  passam a falhar a suite em vez de passar em silêncio.
- `inventory/models.py` e `users-service/models/user.py` — `str, Enum` passou a
  `enum.StrEnum`.
- `api/v1/products/tests/conftest.py` — import `requests` não utilizado
  removido; `tests/unit/test_topicos.py` e os testes dos workers — limpeza de
  variáveis mortas e de comprehensions redundantes.
- Repositório inteiro sem violações do ruff: **144 → 0** (imports ordenados,
  imports mortos removidos, `Optional[X]` → `X | None`, `timezone.utc` →
  `datetime.UTC`, whitespace normalizado).
- `README.md` — secção "Como executar os testes" reescrita para os novos
  comandos e para a execução sem Docker.

### Sem impacto no exterior
- Contrato HTTP `/api/v1/*` inalterado; `docs/openapi.yaml` inalterado; a
  coleção Postman inalterada.

## [Aula 21] — Consulta de Dados em Linguagem Natural (Texto-para-SQL)

### Adicionado
- App `ask_sql` (`api/v1/products/ask_sql/`) com `POST /api/v1/ask_sql`
  (aceita também a forma com barra final).
- Geração de schema a partir de `Model._meta` (`orders_order`, `catalog_item`,
  `catalog_category`) injetada no prompt da LLM.
- Extração do SQL aceitando JSON, JSON em markdown, bloco ` ```sql ` e SQL puro.
- Segurança: allow-list de tabelas/colunas, apenas `SELECT`/`WITH`, bloqueio de
  DML/DDL e comentários, injeção de `LIMIT`, transação read-only no PostgreSQL
  (`SET TRANSACTION READ ONLY`) e `PRAGMA query_only` no SQLite.
- Execução com `statement_timeout`, limite de linhas (`ASK_SQL_MAX_ROWS`) e
  conversão de `Decimal`/data/hora/UUID/bytes para JSON.
- Aba **"Consulta em Linguagem Natural"** no Streamlit, com pergunta, exemplos,
  SQL gerado (`st.code`) e resultados (`st.dataframe`).
- Testes: `test_ask_sql_endpoint.py`, `test_ask_sql_prompts.py`,
  `test_sql_extraction.py`, `test_sql_safety.py` e `test_sql_execution.py`
  (47 testes; suíte completa **270 verdes**, 96%).

### Alterado
- `assist/llm_service.py`: `chamar_llm_com_mensagens()` reutilizável por outros
  apps; `/assist` mantém o contrato. `assist/telemetry.py` aceita `acao`.
- `products/settings.py`/`urls.py`: registo do app e da rota `ask_sql`.
- `products/exceptions.py`: `TITULOS` ganhou `422` (entidade não processável).
- `requirements.txt` (`sqlparse==0.5.3`), `pytest.ini` (`--cov=ask_sql`),
  `dashboard/requirements.txt` (`httpx==0.27.2`) e `docker-compose.yml`
  (envs `ASK_SQL_*` e `API_BASE_URL` no dashboard).
- `docs/openapi.yaml`: tag `Consulta SQL`, path `/api/v1/ask_sql/`, schemas
  `AskSqlEntrada`/`AskSqlResposta`/`AskSqlMeta` e resposta 422 `SQLInvalido`.
- Coleção Postman com a pasta `Consulta SQL` (200/400/422/503).
- `README.md`, `docs/aulas/AULA_21.md`, `docs/INDEX.md` e `PROMPTS.md`.

### Escopo
- Validação automática com provedor fake (offline). A validação com perguntas
  reais contra o provedor LLM exige `LLM_API_KEY` e fica pendente em ambiente
  com chave configurada.
- O endpoint continua anónimo, como o resto da API; a allow-list limita
  mutações, mas não leitura. Autenticação/throttle ficam para aula futura.

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
