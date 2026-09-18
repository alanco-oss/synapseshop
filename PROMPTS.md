# PROMPTS.md

Histórico de uso de IA generativa no desenvolvimento do SynapseShop.

## Registro

### Aula 3 — Docker Essencial: Do Básico ao Compose

#### 1. Dockerfile multistage

- **Ferramenta:** OpenCode
- **Prompt:** "Reveja o plano de conteinerização da Aula 2 e gere um Dockerfile
  para a Aula 3 com multistage build, cache eficiente de dependências e
  execução como usuário não-root, sem antecipar Django REST Framework, FastAPI
  ou PostgreSQL com modelos de dados."
- **Correções aplicadas:** `HEALTHCHECK` usa uma forma inline —
  `python -c "import urllib.request; urllib.request.urlopen(...)"` — pois a
  imagem `python:3.12-slim` não inclui `curl`/`wget`; a forma inline foi
  escolhida (em vez de `python -m`) porque permite tratar exceções e retornar o
  exit code correto que o HEALTHCHECK do Docker precisa para determinar status
  "healthy"/"unhealthy"; dependências instaladas
  com `pip install --user` na stage builder e copiadas para a stage runtime;
  com `requirements.txt` vazio o `pip install --user` não cria `/root/.local`,
  o que quebrava o `COPY --from=builder` — corrigido com `mkdir -p /root/.local`
  após a instalação.
- **Impacto:** imagem menor, executada como usuário não-root e com cache de
  dependências (o `requirements.txt` é copiado antes do código-fonte).

#### 2. Docker Compose (API + Banco de Dados)

- **Ferramenta:** OpenCode
- **Prompt:** "Crie um docker-compose.yml orquestrando a API e o banco de
  dados para a Aula 3, com injeção de variáveis de ambiente mínimas,
  healthcheck do banco e um único comando para subir o ambiente."
- **Correções aplicadas:** PostgreSQL mantido apenas como serviço de
  orquestração (sem models/migrações) para respeitar a regra de não antecipação
  da Aula 6; `api` aguarda o `db` ficar saudável via `depends_on.condition`.
- **Impacto:** `docker compose up` inicia API + banco e a API expõe `/health`.

#### 3. Rota /health

- **Ferramenta:** OpenCode
- **Prompt:** "Implemente a rota /health para monitoramento de disponibilidade
  sem utilizar frameworks (FastAPI/DRF), apenas a biblioteca padrão do Python."
- **Impacto:** `GET /health` responde `200 {"status": "ok", ...}` expondo o
  estado da API e o `DB_HOST` configurado.

### Aula 4 — CRUD da API Principal com Django REST Framework

#### 1. Model, Serializer e ViewSet do Produto

- **Ferramenta:** OpenCode
- **Prompt:** "Definir o Model em `products/models.py` — os campos transacionais
  do recurso (ex: nome, preco, estoque). Criar o Serializer em
  `products/serializers.py`, baseado em ModelSerializer. Criar o ViewSet em
  `products/views.py`, herdando de ModelViewSet. Registrar no Router e conectar
  com a URL versionada `/api/v1/`."
- **Decisões tomadas:** Model `Produto` com `nome` (CharField 200), `preco`
  (DecimalField 10,2) e `estoque` (PositiveIntegerField). `ProdutoSerializer`
  expondo `id`, `nome`, `preco`, `estoque`. `ProdutoViewSet(ModelViewSet)`.
  Router DRF registrando `produtos` sob `/api/v1/`. Banco permanece `sqlite3`
  (PostgreSQL é Aula 6 — sem antecipação). O package `products` atua como app
  (`INSTALLED_APPS`).
- **Impacto:** endpoints CRUD funcionais em `/api/v1/produtos/`.

#### 2. Integração do Django ao Docker (gunicorn)

- **Ferramenta:** OpenCode
- **Prompt:** (sequência) "Integrar Django ao Docker".
- **Problema encontrado e correções aplicadas:**
  - Com o padrão da Aula 3 (`pip install --user` em `/root/.local`), o usuário
    não-root `app` não conseguia executar `gunicorn`
    (`Permission denied` em `/root/.local/bin/gunicorn`). Substituído por
    `python -m venv /opt/venv` no builder e `COPY --from=builder /opt/venv`,
    mantendo multistage e cache de dependências.
  - `requirements.txt` passou a pinar `Django==6.0.7`,
    `djangorestframework==3.18.1` e `gunicorn==26.2.0`.
  - `CMD` agora roda `python manage.py migrate && gunicorn products.wsgi:application
    --bind 0.0.0.0:8000 --workers 2` para a API subir com as tabelas criadas.
  - `db.sqlite3` criado localmente acabava embarcado na imagem via `COPY` —
    resolvido adicionando `*.sqlite3`/`api/v1/products/db.sqlite3` ao
    `.dockerignore` e criando `.gitignore` (`.venv/`, `*.sqlite3`, `__pycache__/`).
  - `HEALTHCHECK` do Dockerfile passou a validar `GET /api/v1/produtos/` (200 do DRF).
- **Impacto:** `docker compose up` levanta API (gunicorn) + banco, contêiner
  `healthy` e CRUD validado via `127.0.0.1:8000`.

#### 3. Checklist "IA-safe" e Coleção Postman

- **Ferramenta:** OpenCode
- **Prompts:** (a) criar o guia de checagem para código gerado por IA (imports,
  tipos de dados, validações customizadas e status HTTP); (b) exportar as rotas
  criadas em uma coleção Postman no diretório do projeto.
- **Correções aplicadas:** 
  - `docs/checklist_ia_safe.md` criado e aplicado aos artefatos da Aula 4.
  - Coleção Postman v2.1 (`postman/collections/SynapseShop API.postman_collection.json`)
    com as 6 operações CRUD e variáveis `baseUrl`/`produto_id`.
  - `.gitignore` corrigido para **versionar** `postman/` (coleção) mantendo
    apenas `.postman/` (metadados locais do app) ignorado.
- **Impacto:** DoD da Aula 4 fechado: DRF integrado, entidades modeladas,
  endpoints `/api/v1/`, status codes corretos (200/201/204/400/404), checklist
  IA-safe e coleção Postman versionados.

#### 4. App de Catálogo (`catalog`) — Categorias e Itens

- **Ferramenta:** OpenCode
- **Prompt:** "Crie o app de catálogo de acordo com o md da aula 4" — a spec
  (`specs/specs_da_aula_4.md`) define as entidades `Category` e `Item` e exige
  os endpoints `/api/v1/categories/` e `/api/v1/items/`.
- **Decisões tomadas:**
  - Criado o app `catalog/` (`apps.py`, `models.py`, `serializers.py`,
    `views.py`, `urls.py`, `migrations/`) registrado em `INSTALLED_APPS` como
    `catalog.apps.CatalogConfig`.
  - `Category`: `nome` (CharField 100, `unique`), `descricao` (TextField
    `blank`). `Item`: `nome`, `descricao`, `preco` (DecimalField 10,2),
    `estoque` (PositiveIntegerField default 0) e `categoria` (ForeignKey
    `SET_NULL`, `null`/`blank`).
  - `ModelSerializer`s com validação de negócio: `validate_preco` rejeita
    preço negativo (`400 Bad Request`); FK inexistente e campo obrigatório
    ausente também retornam `400`.
  - `ModelViewSet`s (`CategoryViewSet`, `ItemViewSet`) registrados em
    `DefaultRouter` sob `/api/v1/` (`catalog/urls.py` iterado em
    `products/urls.py`).
  - O artefato inicial `Produto` (model/serializer/viewset/rota
    `/api/v1/produtos/`, que não satisfazia o DoD da Aula 4) foi removido e o
    pacote `products/` ficou apenas como projeto/config (settings, urls, wsgi).
  - `ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]` para permitir o
    `runserver` local e o `APIClient` do DRF nos testes.
- **Validação (IA-safe):** 15 requisições CRUD via `rest_framework.test.APIClient`
  — `200` (list/retrieve/update), `201` (create), `204` (delete), `400`
  (preço negativo, nome ausente, categoria inexistente) e `404` (id inexistente
  e recurso excluído) — todas passaram. `manage.py check` sem issues e migração
  `catalog/0001_initial` aplicada.
- **Impacto:** endpoints CRUD funcionais em `/api/v1/categories/` e
  `/api/v1/items/`, atendendo integralmente ao DoD da Aula 4. Postman
  (`postman/collections/SynapseShop API.postman_collection.json`) e
  Dockerfile (`HEALTHCHECK` para `/api/v1/items/`) atualizados.

---

*Este arquivo crescerá a cada aula conforme o uso de IA generativa no projeto.*