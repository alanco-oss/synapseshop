# SynapseShop — Documentação do projeto

## Aula 3 — Infraestrutura Docker

### Objetivo

Evolução da conteinerização da Aula 2: imagem otimizada com *multistage build*,
execução como usuário não-root, orquestração da API com o banco de dados via
Docker Compose e rota `/health` para monitoramento básico.

### Estrutura

```
Aula 3/
├── api/                 # Entrypoints e roteamento (Aula 4+)
├── services/            # Lógica de negócio (Aula 4+)
├── repositories/        # Acesso a dados (Aula 6+)
├── specs/               # Especificações do curso
├── .dockerignore
├── app.py               # Servidor HTTP stdlib com rota /health
├── docker-compose.yml   # Orquestração API + PostgreSQL
├── Dockerfile           # Multistage, usuário não-root, cache de deps
└── requirements.txt     # Dependências (vazio na Aula 3)
```

### Como subir o ambiente

Com **um único comando** (preferir a variante sem hífen em versões novas do
Compose; o curso também aceita `docker-compose up`):

```bash
docker compose up --build
```

Para rodar em segundo plano:

```bash
docker compose up -d --build
```

### Validação da rota /health

```bash
curl http://127.0.0.1:8000/health
# {"status": "ok", "app": "synapseshop-api", "db_host": "db"}
```

*Nota:* em máquinas Windows, `curl http://localhost:8000/health` pode atingir um
listener IPv6 do próprio sistema (`dllhost`) em vez do contêiner — prefira
`127.0.0.1`.

O container também possui `HEALTHCHECK` interno (imagem está *healthy* apenas
quando `/health` responde 200).

### Como derrubar os contêineres

```bash
docker compose down        # remove contêineres e a rede
docker compose down -v     # remove também o volume do banco (pgdata)
```

### Monitoramento de logs

```bash
docker compose logs                      # logs de todos os serviços
docker compose logs -f api               # segue os logs da API em tempo real
docker compose logs -f db                # logs do PostgreSQL
docker compose ps                        # estado dos serviços
```

### Análise das camadas da imagem

```bash
docker history synapseshop-api:latest    # ou docker history aula3-api
```

Use `--no-trunc` para ver o comando completo de cada camada.

### Variáveis de ambiente

As variáveis essenciais são injetadas pelo Compose com valores padrão
(sobrescrevíveis via arquivo `.env` ou variáveis do shell):

| Serviço | Variável | Padrão |
|---|---|---|
| `api` | `APP_NAME` | `synapseshop-api` |
| `api` | `APP_HOST` | `0.0.0.0` |
| `api` | `APP_PORT` | `8000` |
| `api` | `DB_HOST` | `db` |
| `db` | `POSTGRES_USER` | `synapse` |
| `db` | `POSTGRES_PASSWORD` | `synapseshop` |
| `db` | `POSTGRES_DB` | `synapseshop` |

### Escopo da Aula 3

Apenas infraestrutura de conteinerização. **Não** foram antecipados: Django
REST Framework, FastAPI, modelos de banco de dados, migrações, mensageria ou
lógicas de IA (Aulas futuras). O PostgreSQL roda apenas como serviço de
orquestração, sem código de acesso a dados.

---

## Aula 8 — Cache-aside com Redis

### Objetivo

Otimizar os endpoints de pedidos com o padrão *cache-aside*: o Redis é
consultado antes do banco, preenchido no *miss* e invalidado por evento de
domínio, com TTL como rede de segurança.

### Chaves e TTL

| Endpoint | Chave lógica | Chave física no Redis | TTL |
|---|---|---|---|
| `GET /api/v1/pedidos/` | `pedidos:list` | `synapseshop:1:pedidos:list` | 60s (`REDIS_TTL_LISTA`) |
| `GET /api/v1/pedidos/{id}/detalhes/` | `pedido:{id}` | `synapseshop:1:pedido:{id}` | 300s (`REDIS_TTL_DETALHES`) |

A nomenclatura é centralizada em `orders/cache.py` (`chave_lista`,
`chave_detalhes`); o prefixo `synapseshop:1:` vem do `KEY_PREFIX` do Django. Os
contadores de métricas usam `cache:metricas:{endpoint}:{hits|misses}` e **não**
recebem TTL, para que o hit rate seja acumulado entre reinícios.

### Estratégia de invalidação

A invalidação é por evento de domínio, não por tempo. O TTL existe apenas como
rede de segurança para o caso de um evento não previsto.

| Evento | Operação | Chaves invalidadas |
|---|---|---|
| `PedidoCriado` | `POST /api/v1/pedidos/` | `pedidos:list` |
| `PedidoAtualizado` | `PUT`/`PATCH /api/v1/pedidos/{id}/` | `pedido:{id}` e `pedidos:list` |
| `PedidoRemovido` | `DELETE /api/v1/pedidos/{id}/` | `pedido:{id}` e `pedidos:list` |

A lista é invalidada junto com o detalhe porque qualquer alteração de um pedido
muda o conteúdo da listagem — deixá-la em cache serviria dados obsoletos. Não é
usada *write-through*: o cache é sempre reconstruído a partir do banco no
próximo *miss*.

Cada evento gera log estruturado, por exemplo:

```
orders.cache evento=PedidoAtualizado pedido_id=502 chaves=pedido:502,pedidos:list acao=invalidate
```

### Ciclo *miss* → preenchimento → *hit*

```bash
docker exec synapseshop-redis redis-cli -n 1 DEL "synapseshop:1:pedidos:list"

curl -s http://127.0.0.1:8000/api/v1/pedidos/ > /dev/null   # log: cache=miss + cache=preenchido
curl -s http://127.0.0.1:8000/api/v1/pedidos/ > /dev/null   # log: cache=hit

docker exec synapseshop-redis redis-cli -n 1 TTL "synapseshop:1:pedidos:list"
docker exec synapseshop-redis redis-cli -n 1 EXISTS "synapseshop:1:pedido:1"
```

### Métricas de eficácia (hit rate)

```bash
curl -s http://127.0.0.1:8000/api/v1/pedidos/metricas-cache/
```

```json
{"lista":{"hits":3207,"misses":206,"lookups":3413,"hit_rate":0.9396},
 "detalhes":{"hits":1067,"misses":162,"lookups":1229,"hit_rate":0.8682}}
```

`hit_rate = hits / lookups`, mantido por endpoint. O mesmo dado fica disponível
nos logs estruturados (`cache=hit` / `cache=miss`), então o endpoint de métricas
pode ser desativado sem perder a observabilidade. Um `404` de detalhe conta como
*miss* e **não** é cacheado.

Os contadores não recebem TTL e sobrevivem a reinícios, então o hit rate é
acumulado desde o primeiro acesso. Para zerá-los, sem tocar no cache de dados:

```bash
docker exec synapseshop-redis redis-cli -n 1 DEL \
  "synapseshop:1:cache:metricas:lista:hits" \
  "synapseshop:1:cache:metricas:lista:misses" \
  "synapseshop:1:cache:metricas:detalhes:hits" \
  "synapseshop:1:cache:metricas:detalhes:misses"
```

### Degradação graciosa

Se o Redis estiver indisponível, nenhuma requisição quebra: as operações de
cache são envolvidas e o erro vira log `cache=indisponivel`, o viewset cai no
banco e responde normalmente. Verificado com o contêiner parado — lista,
detalhes e métricas continuaram em `200`, apenas com pior latência.

### Medições de desempenho

Comparação antes/depois do cache via `scripts/medir_cache.py`, com **500 pedidos**
na base. O script mede quatro fases do mesmo recurso:

- `sem_cache` — consulta ao ORM + serializer, sem cache e sem HTTP: é o custo
  do caminho de dados que existia antes da Aula 8;
- `cache_miss` — endpoint real com a chave apagada antes de cada requisição
  (*lookup* no Redis + banco + preenchimento);
- `cache_hit` — endpoint real com a chave aquecida, **mesma concorrência do
  `cache_miss`**, para comparação direta;
- `cache_hit_carga` — endpoint aquecido sob concorrência, para medir vazão.

```bash
api/v1/products/.venv/Scripts/python scripts/medir_cache.py --endpoint lista --seed 500 --requisicoes 300 --requisicoes-miss 100
api/v1/products/.venv/Scripts/python scripts/medir_cache.py --endpoint detalhes --id 1 --requisicoes 300 --requisicoes-miss 100
```

`--seed 500` garante 500 pedidos na base (cria os que faltarem) e
`--requisicoes-miss 100` é o tamanho da amostra do caminho frio, que é
sequencial e por isso mais caro. Para silenciar o log por requisição durante a
medição, use `CACHE_LOG_LEVEL=ERROR` (ou `--verbose` para mantê-lo).

`GET /api/v1/pedidos/` (500 pedidos, threads = 1, salvo a fase de carga):

| fase | cenário | req. | média (ms) | p95 (ms) | RPS |
|---|---|---|---|---|---|
| `sem_cache` | ORM + serializer | 100 | 43.81 | 73.20 | 22.8 |
| `cache_miss` | endpoint, chave apagada | 100 | 67.17 | 117.52 | 14.9 |
| `cache_hit` | endpoint, chave aquecida | 100 | 14.13 | 19.44 | 70.7 |
| `cache_hit_carga` | endpoint aquecido (10 threads) | 300 | 79.31 | 159.88 | 122.4 |

`GET /api/v1/pedidos/{id}/detalhes/` (pedido 1):

| fase | cenário | req. | média (ms) | p95 (ms) | RPS |
|---|---|---|---|---|---|
| `sem_cache` | ORM + serializer | 100 | 3.64 | 4.44 | 272.6 |
| `cache_miss` | endpoint, chave apagada | 100 | 22.35 | 43.29 | 44.7 |
| `cache_hit` | endpoint, chave aquecida | 100 | 9.57 | 12.88 | 104.4 |
| `cache_hit_carga` | endpoint aquecido (10 threads) | 300 | 61.07 | 118.41 | 159.3 |

Resultados, comparando sempre fases com a mesma concorrência:

- **Listagem:** 67.17 ms → 14.13 ms de média (≈4.8× mais rápido) e 14.9 → 70.7
  RPS; o p95 cai de 117.52 ms para 19.44 ms.
- **Detalhe:** 22.35 ms → 9.57 ms (≈2.3×) e 44.7 → 104.4 RPS.
- O ganho no detalhe é menor porque uma linha buscada pela chave primária já é
  barata (3.64 ms): o cache paga uma ida e volta ao Redis. O cache vale a pena
  quando a consulta é pesada ou concorrente — daí os 122.4 RPS da listagem e os
  159.3 RPS do detalhe com 10 threads, já que nenhuma requisição chega ao banco.
- Em produção o ganho tende a ser maior: aqui o PostgreSQL e o Redis estão no
  mesmo host, então a latência de rede é quase nula.
- Entre execuções há variação (o caminho frio depende do estado do cache de
  páginas do PostgreSQL): a listagem medida em outra rodada foi de 82.99 ms no
  *miss* e 13.91 ms no *hit*, o mesmo intervalo de ganho. O script imprime os
  números da própria execução — use-os como referência, não como constante.

Ambiente das medições: Windows, Python 3.13 (venv), Django 6.1.1, PostgreSQL e
Redis 7 em contêiner, requisições em processo via WSGI do Django (sem socket),
para que a diferença medida seja o efeito do cache e não o da rede. O mesmo
ciclo (miss → preenchimento → hit, TTL, invalidação e degradação graciosa com o
Redis parado) foi repetido no contêiner com as versões pinadas em
`requirements.txt`, Django 6.0.7 e redis-py 8.1.0.

### Variáveis de ambiente da Aula 8

| Variável | Padrão | Uso |
|---|---|---|
| `REDIS_URL` | `redis://127.0.0.1:6379/1` | Conexão do cache |
| `REDIS_TTL_LISTA` | `60` | TTL da listagem |
| `REDIS_TTL_DETALHES` | `300` | TTL do detalhe |
| `CACHE_LOG_LEVEL` | `INFO` | Nível do log `orders.cache` (`ERROR` silencia o ruído de *miss*/*hit*) |

No Compose, o serviço `api` recebe `DB_HOST`, `POSTGRES_*` e `REDIS_URL`, e só
sobe depois que `db` e `redis` estão saudáveis:

```bash
docker compose up -d --build
docker compose exec redis redis-cli -n 1 KEYS "synapseshop*"
```

### Escopo da Aula 8

Apenas cache-aside dos pedidos. **Não** foram antecipados: cache do catálogo,
mensageria assíncrona (Kafka/RabbitMQ, Aulas 9–11), modelos novos
(`OrderItem`), autenticação ou *placeholder*s de funcionalidades futuras.
