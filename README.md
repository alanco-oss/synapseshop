# SynapseShop — Documentação do projeto

[![CI](https://github.com/alanco-oss/synapseshop/actions/workflows/ci.yml/badge.svg)](https://github.com/alanco-oss/synapseshop/actions/workflows/ci.yml)

## Comandos de operação

Todos os comandos recorrentes do projeto estão centralizados em `tasks.py`
(Python puro — funciona igual em Windows, Linux e macOS, sem instalar nada).

```bash
python tasks.py --help        # lista completa
python tasks.py test          # suite de testes (270 testes, ~4s, sem Docker)
python tasks.py coverage      # suite + relatório HTML de cobertura
python tasks.py lint          # ruff + lint do contrato OpenAPI (Spectral)
python tasks.py check         # lint + testes: verificação antes do commit
python tasks.py up            # sobe o stack completo via docker compose
python tasks.py down          # derruba o stack e remove os volumes
python tasks.py clean         # remove caches e artefactos
```

A suíte de testes **não precisa de Docker, Postgres, Redis nem Kafka**: corre
em SQLite em memória com *fakes* para as dependências externas. Para validar
contra o PostgreSQL de produção, `DB_ENGINE=postgres pytest`.

A CI (`.github/workflows/ci.yml`) corre a suíte nos dois motores de base de
dados, aplica o linter e o lint do OpenAPI, e constrói as imagens Docker.
O funcionamento detalhado e a configuração de segredos estão na
[secção da Aula 22](#aula-22--pipeline-de-cicd-com-github-actions).

---


## Documentacao por Aula

- [Aula 03](docs/aulas/AULA_03.md)
- [Aula 08](docs/aulas/AULA_08.md)
- [Aula 09](docs/aulas/AULA_09.md)
- [Aula 10](docs/aulas/AULA_10.md)
- [Aula 11](docs/aulas/AULA_11.md)
- [Aula 12](docs/aulas/AULA_12.md)
- [Aula 13](docs/aulas/AULA_13.md)
- [Aula 14](docs/aulas/AULA_14.md)
- [Aula 21](docs/aulas/AULA_21.md)
- [Aula 22](docs/aulas/AULA_22.md)

## Documentacao Adicional

- [AGENTS.md](AGENTS.md)
- [docs/INDEX.md](docs/INDEX.md)
- [CHANGELOG.md](CHANGELOG.md)
- [docs/openapi.yaml](docs/openapi.yaml)
- [postman/](postman/)
- [specs/](specs/)


## Aula 19 - Conexao Segura, SQL Injection e Painel Streamlit

### Executar
```bash
python tasks.py up
# ou
docker compose up --build
```

Painel disponivel em: **http://localhost:8501** (health: `http://localhost:8501/_stcore/health`).
O servico `dashboard` usa bind-mount em `./dashboard:/app`, por isso alteracoes no
codigo refletem em tempo real (live reload).

### Variaveis de ambiente (Dashboard)
| Variavel | Padrao | Descricao |
|---|---|---|
| DB_HOST | db (compose) / localhost | Host do PostgreSQL |
| DB_PORT | 5432 | Porta |
| DB_NAME / POSTGRES_DB | synapseshop | Banco de dados |
| DB_USER / POSTGRES_USER | synapse | Usuario |
| DB_PASSWORD / POSTGRES_PASSWORD | synapseshop | Senha |
| DB_SSLMODE | require (codigo) / prefer (compose local) | Modo SSL/TLS |
| API_BASE_URL | http://api:8000 (compose) | Base URL da API para consumo de métricas (Aula 20) |

> O PostgreSQL do `docker-compose.yml` nao tem TLS configurado. No ambiente local o
> compose injeta `DB_SSLMODE=prefer` (tenta TLS e recorre a ligacao normal). Em
> producao defina `DB_SSLMODE=require`.

### Seguranca
- Zero Interpolacao: Todas as consultas SQL utilizam text() com bind parameters.
- SQL Injection: Filtros dinamicos devem usar allow-list. Listas utilizam = ANY(:lista).
- Conexao: SQLAlchemy com pool_pre_ping, timeouts e connect_args com sslmode configuravel.

## Aula 20 - Dashboard de Desempenho da API em Streamlit

### Objetivo
Painel de observabilidade/desempenho integrado à API de pedidos (Aula 11), com métricas de performance, cache e mensageria.

### Como subir e acessar
```bash
# Stack completa
docker compose up -d --build

# Apenas dashboard
docker compose up -d dashboard
```

- **Acesso:** http://127.0.0.1:8501
- **Health:** http://127.0.0.1:8501/_stcore/health

### Funcionalidades
- **Aba "Desempenho da API":** KPIs (total de requisições/publicações, latência média/p95, taxa de erro %), gráficos de latência/throughput, distribuição de status (2xx/4xx/5xx), eficiência de cache e notificações.
- **Aba "Pedidos (Analítico)":** Visão analítica existente mantida (filtros por período/status, totais, gráficos por status/data).
- **Filtros interativos:** Componente, classes de status HTTP e janela de visualização.
- **Otimização:** `@st.cache_data` aplicado às consultas/métricas.
- **Integração:** Consome `GET /api/v1/pedidos/metricas-cache/` e `GET /api/v1/pedidos/metricas-mensageria/` via `API_BASE_URL`.

## Aula 21 - Consulta de Dados em Linguagem Natural (Texto-para-SQL)

### Objetivo
Permitir perguntas de negócio em português, traduzidas em SQL pela LLM,
executadas em modo somente leitura e apresentadas no painel Streamlit.

### Endpoint
`POST /api/v1/ask_sql` (aceita também `/api/v1/ask_sql/`)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ask_sql \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: demo-aula-21" \
  -d '{"question": "Quais os 5 últimos pedidos?"}'
```

Pedido:

```json
{"question": "Quais os 5 últimos pedidos?", "temperature": 0.0, "max_tokens": 512}
```

Resposta `200`:

```json
{
  "question": "Quais os 5 últimos pedidos?",
  "sql": "SELECT id, status, total, created_at FROM orders_order ORDER BY created_at DESC LIMIT 5",
  "columns": ["id", "status", "total", "created_at"],
  "results": [{"id": 12, "status": "paid", "total": 129.9, "created_at": "2026-01-15T12:00:00Z"}],
  "row_count": 1,
  "truncated": false,
  "meta": {"tokens_prompt": 320, "tokens_output": 42, "llm_ms": 840.5, "execution_ms": 3.2}
}
```

Erros: `400` payload inválido, `422` SQL insegura/inválida ou falha de
execução, `502` erro determinístico do provedor e `503` provedor
indisponível/circuito aberto (envelope RFC 7807).

### Tabelas expostas à LLM
- `orders_order` (pedidos)
- `catalog_item` (itens)
- `catalog_category` (categorias)

As tabelas `users`/`tokens` do `users-service` ficam fora do contexto. Não
existem, no domínio atual, tabelas de endereços ou pagamentos.

### Segurança
- Apenas uma instrução `SELECT` (ou `WITH ... SELECT`) por pedido.
- Allow-list de tabelas e bloqueio de DML/DDL (`INSERT`, `UPDATE`, `DELETE`,
  `DROP`, `ALTER`, etc.), comentários e múltiplas instruções.
- Execução em transação read-only no PostgreSQL (`SET TRANSACTION READ ONLY`)
  e `PRAGMA query_only` no SQLite dos testes.
- `statement_timeout` configurável, `LIMIT` aplicado quando ausente e limite
  máximo de linhas devolvidas.
- Pergunta redigida (PII/segredos) antes de sair para o provedor.

### Interface Streamlit
A aba **"Consulta em Linguagem Natural"** disponibiliza campo de pergunta,
exemplos, e exibe o SQL gerado (`st.code`) e o resultado em `st.dataframe`.
Sobe com `docker compose up -d --build` e abre em http://127.0.0.1:8501.

### Variáveis de ambiente (API)
| Variável | Padrão | Descrição |
|---|---|---|
| ASK_SQL_MAX_ROWS | 100 | Máximo de linhas devolvidas |
| ASK_SQL_TIMEOUT_MS | 5000 | Timeout da execução no PostgreSQL |
| ASK_SQL_MAX_QUESTION_LENGTH | 1000 | Tamanho máximo da pergunta |
| ASK_SQL_DEFAULT_MAX_TOKENS | 512 | Tokens máximos da resposta da LLM |

Reutiliza `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT`,
`LLM_RETRIES`, backoff e circuito da Aula 14.

---

## Aula 22 — Pipeline de CI/CD com GitHub Actions

### Objetivo
Automatizar a verificação de cada *commit*/*pull request*: lint, testes nos dois
motores de base de dados e validação do *build* das imagens Docker. A entrega
contínua (publicação em *registry* e *deploy*) fica para a Aula 23.

### Gatilhos
| Evento | Configuração |
|---|---|
| `push` | branches `master` e `main` |
| `pull_request` | direcionado a `master`/`main` |
| `workflow_dispatch` | execução manual na aba **Actions** |

### Jobs
| Job | Runner | O que faz |
|---|---|---|
| `test-and-lint` | `ubuntu-latest` | *checkout*, setup do Python 3.12, instala dependências, `ruff check .`, Spectral no OpenAPI e `pytest` em matriz SQLite/PostgreSQL |
| `docker-build` | `ubuntu-latest` | valida o `docker-compose.yml` e constrói `synapseshop-api:test` e `synapseshop-inventory:test`; só corre depois dos testes passarem |

- A matriz `engine: [sqlite, postgres]` garante que nenhuma *query* depende do
  motor; o PostgreSQL sobe como serviço efémero do job.
- O *gate* de cobertura (`COVERAGE_MIN=95`) falha o pipeline se a cobertura cair.
- O relatório `.coverage` é publicado como artefacto na perna SQLite.
- O Spectral corre apenas uma vez (perna SQLite) para não duplicar trabalho.

### Reproduzir localmente
```bash
python tasks.py check   # ruff + Spectral + pytest
python tasks.py build   # docker compose build
```

### Segredos e variáveis
Nada sensível é commitado (`.env` está no `.gitignore`). Configure em
**Settings → Secrets and variables → Actions**:

| Nome | Obrigatório | Uso |
|---|---|---|
| `SECRET_KEY` | opcional | Chave Django em produção/CI; sem ela o workflow usa `ci-insecure-secret-key` |
| `LLM_API_KEY` | não (CI atual) | Os testes usam provedor falso; será necessária em testes de integração/CD |
| `POSTGRES_*` | não | Credenciais efémeras do serviço PostgreSQL do job, definidas no próprio workflow |

```bash
# GitHub CLI (opcional)
gh secret set SECRET_KEY
gh secret set LLM_API_KEY
```

> O projeto usa `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`/`DB_HOST`/
> `DB_PORT`; não existe `DB_URL` no código atual.

### Validação
O resultado de cada execução fica em **Actions → CI**. O *badge* no topo do
README reflete o estado do branch predefinido. Para inspecionar localmente o
YAML antes de fazer *push*:

```bash
docker run --rm -v "${PWD}:/repo" mikefarah/yq:4 eval /repo/.github/workflows/ci.yml
```

### Documentação relacionada
- [docs/aulas/AULA_22.md](docs/aulas/AULA_22.md)
- [.github/workflows/ci.yml](.github/workflows/ci.yml)
- [specs/spec_da_aula_22.md](specs/spec_da_aula_22.md)
