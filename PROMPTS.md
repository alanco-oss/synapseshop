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

### Aula 8 — Cache-aside com Redis

#### 1. Dependência, infraestrutura e configuração

- **Ferramenta:** OpenCode
- **Prompt:** "Implemente a spec `specs/specs_da_aula_8.md` (cache-aside com
  Redis) starting pela configuração: adicione o cliente Redis, um serviço no
  Compose com healthcheck e o backend de cache do Django apontando para ele."
- **Decisões tomadas:**
  - `redis==8.1.0` em `requirements.txt` — o `RedisCache` do Django 6 fala
    Redis por `redis-py`, que ainda não é dependência padrão do DRF/Django.
  - `CACHES['default']` com `BACKEND`
    `django.core.cache.backends.redis.RedisCache`, `LOCATION` a partir de
    `REDIS_URL` (db 1) e `KEY_PREFIX: synapseshop`, o que isola as chaves da
    aplicação e facilita a inspeção manual no `redis-cli`.
  - `socket_connect_timeout`/`socket_timeout` de 2s para que uma falha de rede
    no Redis não vire uma requisição pendurada.
  - Serviço `redis:7-alpine` no Compose com healthcheck e
    `depends_on: condition: service_healthy` no serviço `api`.
  - Backend escolhido pelo usuário entre as opções apresentadas; o cache do
    catálogo foi explicitamente deixado fora do escopo, e nenhuma
    `CELERY`/Kafka/RabbitMQ foi antecipada (Aulas 9–11).
- **Correções aplicadas:** o Docker Desktop não estava inicializado durante a
  validação; após reinício, `docker compose ps` mostrou `db` e `redis` saudáveis.
  `REDIS_URL` não é necessária para o `runserver` local, que usa o padrão
  `127.0.0.1:6379`.

#### 2. App de pedidos: serializer, viewset e rotas

- **Ferramenta:** OpenCode
- **Prompt:** "Crie o app de pedidos seguindo a spec da Aula 8: serializer,
  viewset com listagem e um endpoint de detalhes mais pesado, ambos com
  cache-aside."
- **Decisões tomadas:**
  - `OrderSerializer` com campos explícitos (`id`, `user_id`, `status`, `total`,
    `created_at`) — `created_at` somente leitura, para a spec não exigir um
    campo de data no corpo do `POST`.
  - `validate_total` rejeita total negativo (`400`), alinhando o app ao
    tratamento de regras de negócio já usado no catálogo.
  - `list()` e a ação `detalhes` (`@action(detail=True)`) são os dois pontos
    cacheados; as demais operações do `ModelViewSet` seguem delegando ao ORM.
  - `products/urls.py` passou a incluir `orders.urls` sob `/api/v1/`, gerando
    `/api/v1/pedidos/` e `/api/v1/pedidos/{id}/detalhes/`.

#### 3. Camada de cache, métricas e invalidação

- **Ferramenta:** OpenCode
- **Prompt:** "Implemente a camada de cache: chaves `pedidos:list` e
  `pedido:{id}` com TTL, contadores de hit/miss no Redis, invalidação por evento
  de domínio e degradação graciosa quando o cache está fora."
- **Decisões tomadas:**
  - Toda a nomenclatura e TTL vivem em `orders/cache.py`, para que nenhum
    viewset monte chave na mão.
  - Métricas como contadores Redis (`cache:metricas:{endpoint}:{hits|misses}`)
    sem TTL, expostas em `GET /api/v1/pedidos/metricas-cache/` com
    `hit_rate = hits/lookups`, exatamente como a spec sugere.
  - Invalidação por evento: `PedidoCriado` limpa a lista;
    `PedidoAtualizado` e `PedidoRemovido` limpam `pedido:{id}` **e** a lista.
  - Toda operação de cache é envolvida por um helper que converte
    `RedisError` em log `cache=indisponivel` e devolve `None`, deixando o
    endpoint cair no banco — cache nunca derruba a API.
  - Um `404` de detalhe conta como *miss* e não é cacheado.
- **Correções aplicadas:** os eventos de domínio estavam fixos no log
  (`evento=PedidoCriado|PedidoRemovido` na criação e `PedidoAtualizado` na
  remoção, que é enganoso); `invalidar_lista`/`invalidar_pedido` passaram a
  receber o nome do evento, e `perform_destroy` registra `PedidoRemovido`.
  Além disso, o log dizia `cache=preenchido` mesmo quando a escrita falhava
  (o helper engolia o `RedisError` e devolvia `None`, indistinguível de sucesso);
  a gravação passou por um `_preencher` que só confirma o preenchimento quando o
  `cache.set` realmente retorna.
- **Impacto:** cache-aside ativo nos dois endpoints, com 6 chaves vivas no Redis
  (`pedidos:list`, `pedido:{id}` e os 4 contadores) e invalidação verificada.

#### 4. Validação (IA-safe)

- **Ferramenta:** OpenCode
- **Prompt:** "Valide o comportamento na API em execução: miss, preenchimento,
  hit, TTL, invalidação, 404, 400 e o que acontece com o Redis parado."
- **Validação no venv:** `manage.py check` sem issues e `migrate` sem
  pendências. `miss` seguido de `hit` na lista e no detalhe; TTL observado de
  51s (lista) e 291s (detalhe) contra os 60/300 configurados; `PATCH` removendo
  as duas chaves (`EXISTS` = 0); detalhe inexistente em `404` sem cache; total
  negativo em `400`; com o contêiner do Redis parado, lista, detalhes e métricas
  seguiram em `200`. Logs confirmam `cache=miss`, `cache=preenchido`,
  `cache=hit`, `cache=indisponivel` e os eventos `PedidoCriado`,
  `PedidoAtualizado` e `PedidoRemovido`.
- **Correções aplicadas ao subir o ambiente:** três problemas impediam validar a
  Aula 8 dentro do contêiner, todos anteriores a ela — `requirements.txt` fixava
  `alembic==1.20.1`, versão inexistente no PyPI (a última é 1.20.0), o que
  quebrava `docker compose build api` antes mesmo de instalar o Redis;
  `DATABASES` no `settings.py` tinha `localhost` fixo e o serviço `api` não
  recebia `DB_HOST`, então o gunicorn não alcançava o PostgreSQL (o `settings.py`
  passou a ler `POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD`/`DB_HOST`/
  `DB_PORT` do ambiente, mantendo `localhost` como padrão para o runserver local,
  e o Compose passou a injetar as variáveis); e o `.dockerignore` não excluía
  `.venv`, então os 57 MB do ambiente virtual do Windows iam parar na imagem.
- **Validação no contêiner** (Django 6.0.7 e redis-py 8.1.0, os pins do
  `requirements.txt`): `docker compose up -d --build api` deixa os três serviços
  saudáveis; `miss` → `preenchido` → `hit` na lista e no detalhe; TTL de 58s e
  299s; criação invalida a lista, leitura repovoa o detalhe, `PATCH` e `DELETE`
  invalidam as duas chaves; `404` para id inexistente; `/metricas-cache/`
  respondendo; e com o `redis` parado os três endpoints seguem em `200`, com
  apenas `cache=indisponivel` nos logs e o cache voltando a funcionar sozinho
  quando o contêiner sobe de novo.

#### 5. Medições e documentação

- **Ferramenta:** OpenCode
- **Prompt:** "Crie um script que compare o desempenho antes e depois do cache
  (latência média, p95 e RPS) e registre os resultados no README."
- **Decisões tomadas:**
  - `scripts/medir_cache.py` usa apenas a biblioteca padrão: mede quatro fases
    do mesmo recurso — `sem_cache` (ORM + serializer, o caminho de dados
    anterior), `cache_miss` (chave apagada antes de cada requisição), `cache_hit`
    na **mesma** concorrência do *miss* e `cache_hit_carga` sob 10 threads.
  - O caminho frio roda com concorrência 1 de propósito: em paralelo uma thread
    pode aquecer a chave antes da consulta da outra e a medição seria
    contaminada.
  - As requisições passam pelo WSGI do Django em processo (`APIClient`), sem
    socket, para que a diferença medida seja o efeito do cache e não o da rede.
- **Correções aplicadas:** a primeira versão apagava `cache.make_key(chave)`
    numa chave já prefixada, o que gerava `synapseshop:1:synapseshop:1:...` e
    não deletava a chave alguma — a fase "miss" media, na verdade, *hits*. O
    `make_key` duplicado foi removido; a fase `sem_cache` inicialmente media um
    Redis apontado para uma porta fechada, o que media timeouts em vez do
    caminho de dados, e passou a medir o ORM + serializer diretamente.
- **Resultados (500 pedidos, mesa local):** listagem 67.17 ms → 14.13 ms de
  média (≈4.8×, 14.9 → 70.7 RPS e p95 de 117.52 ms → 19.44 ms); detalhe
  22.35 ms → 9.57 ms (≈2.3×, 44.7 → 104.4 RPS). O detalhe por chave primária já
  é barato (3.64 ms), então o ganho é menor e a análise disso está no README;
  sob 10 threads a listagem chega a 122.4 RPS e o detalhe a 159.3 RPS.
- **Impacto:** `README.md` reestruturado com um capítulo por aula, incluindo
  chaves e TTL, regra de invalidação, degradação graciosa, métricas e as tabelas
  de medição; `PROMPTS.md` e a coleção Postman (`pasta Pedidos`, com
  `pedido_id`) atualizados.

---

### Aula 11 — Desafio Mão na Massa: Núcleo do Mini-Backend

#### 1. Endpoint de simulação de pagamento

- **Ferramenta:** OpenCode
- **Prompt:** "Implemente a ação `POST /api/v1/pedidos/{id}/pagar/` que simula o
  pagamento de um pedido pendente: `aprovado=true` transiciona `pending → paid`,
  invalida o cache e publica o evento `PagamentoSimulado`; `aprovado=false`
  mantém `pending` mas publica o evento na mesma; respostas 200/402/409 e 400
  para payload inválido."
- **Decisões tomadas:**
  - Ação `detail=True` no `OrderViewSet` (reutiliza o router existente) em vez
    de um recurso `pagamentos` separado — o pagamento é um ato *sobre* o pedido.
  - `PagamentoSimuladoSerializer` com `aprovado` (default `true`) e rejeição
    explícita de campos desconhecidos (400) conforme o checklist IA-safe.
  - **402** para recusa (DRF define `HTTP_402_PAYMENT_REQUIRED`).
- **Correções aplicadas:** a primeira versão publicava o evento no tópico
  **padrão** `pedidos.criado` (o default do produtor), enviando `PagamentoSimulado`
  para o worker errado → 2 mensagens em DLQ; corrigido passando
  `topico=topicos.TOPICO_PAGAMENTO` explicitamente. Também corrigida a constante
  (`HTTP_402_PAYMENT_REQUESTED` não existe no DRF → `HTTP_402_PAYMENT_REQUIRED`).
- **Impacto:** endpoint com dois desfechos demonstrados (200/402) e validação de
  payload explícita.

#### 2. Worker de notificação e tópicos

- **Ferramenta:** OpenCode
- **Prompt:** "Crie o management command `consumir_pagamento` (mesmo padrão do
  `consumir_pedido_criado`: commit manual, idempotência via Redis com namespace
  próprio, retry/backoff e DLQ `pedidos.pagamento.dlq`) que consome
  `PagamentoSimulado`, garante o estado do pedido, invalida o cache e emite a
  notificação simulada por log."
- **Decisões tomadas:**
  - Novo comando + serviço `worker-notificacoes` no compose (em vez de estender
    `consumir_pedido_criado`), preservando a semântica e o `--scale worker=3`
    da Aula 10.
  - Marcador Redis `…:feito:` (`idempotencia.concluir/ja_concluido`) para
    distinguir duplicado de falha entre a reserva e a notificação.
  - Contador `notificacoes` (com `aprovado`/`recusado`) em `metricas.py`,
    exposto no endpoint de métricas.
- **Impacto:** fluxo criar → pagar → notificar operante, com DLQ validada
  (`MENSAGERIA_FORCAR_FALHA=1`).

#### 3. Observabilidade e orquestração

- **Ferramenta:** OpenCode
- **Prompt:** "Adicione a rota `GET /health` na API Django (db obrigatório →
  503; redis/kafka → `degraded` mas 200, coerente com a degradação graciosa das
  Aulas 8/9) e ajuste Dockerfile e docker-compose: healthcheck do `api` sobre
  `/health` e `healthcheck: disable` nos workers (não servem HTTP)."
- **Decisões tomadas:** teste de alcancabilidade do Kafka por TCP com timeout
  curto (`HEALTH_TIMEOUT_KAFKA`) para não bloquear o healthcheck.
- **Impacto:** `docker compose ps` mostra todos os serviços `healthy` (os
  workers deixaram de ficar `unhealthy`); `GET /health` devolve o estado das
  três dependências.

---

*Este arquivo crescerá a cada aula conforme o uso de IA generativa no projeto.*