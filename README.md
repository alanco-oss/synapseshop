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

---

## Aula 9 — Mensageria assíncrona com Kafka

### Objetivo

Publicar o evento `PedidoCriado` no `POST /api/v1/pedidos/` e processá-lo num
*worker* assíncrono, com idempotência por dedupe com TTL, reentrega com
*backoff* exponencial e encaminhamento para DLQ após *N* tentativas.

### Escolha do broker: Apache Kafka (Redpanda)

O broker é **Apache Kafka**, executado localmente via
[Redpanda](https://redpanda.com) (imagem `redpandadata/redpanda`), que fala o
protocolo Kafka sem JVM — binário único, arranque em segundos e consumidor
`rpk` embutido para inspeção de tópicos. As razões da escolha:

- **Aula 10 já exige Kafka** (partições, semântica de offset, retenção):
  começar por Kafka evita uma migração de RabbitMQ para Kafka entre aulas.
- **Reentrega e DLQ sob o nosso controlo**: o consumidor confirma offsets
  manualmente (`enable_auto_commit=False`), logo a política de tentativas e o
  caminho para a DLQ são código explícito e auditável, não configuração
  opaca do broker.
- **Chave de partição** = `idempotency_key`, garantindo que o mesmo pedido é
  sempre tratado na mesma partição e na mesma ordem.

Tópicos: `pedidos.criado` (principal), `pedidos.criado.dlq` (mensagens
esgotadas). Ambos são auto-criados pelo Redpanda no primeiro acesso.

### Contrato da mensagem `PedidoCriado`

Definido em `orders/mensageria/contrato.py`, JSON UTF-8 no tópico
`pedidos.criado`:

```json
{
  "event_id": "9f0c1e7e-5f6b-4a1e-9a1e-3d2c8b7f4a11",
  "event_type": "PedidoCriado",
  "occurred_at": "2026-10-07T12:00:00+00:00",
  "idempotency_key": "pedido:42",
  "payload": {
    "pedido_id": 42,
    "user_id": 7,
    "total": "129.90",
    "status": "pending",
    "created_at": "2026-10-07T11:59:59+00:00"
  }
}
```

| Campo | Papel |
|---|---|
| `event_id` | UUID por mensagem, só para rastreio (**não** serve de dedupe) |
| `event_type` | Discriminador do evento |
| `occurred_at` | Instante da ocorrência; base do `latencia_ms` do *worker* |
| `idempotency_key` | **Chave de negócio** `pedido:{id}` — a mesma entrega produz sempre a mesma chave |
| `payload` | Campos mínimos do pedido (`pedido_id`, `user_id`, `total`, `status`, `created_at`) |

`contrato.validar()` rejeita eventos fora do formato; um evento inválido
repete as tentativas e acaba na DLQ (falha permanente).

### Produtor

`POST /api/v1/pedidos/` → `OrderViewSet.perform_create`
(`orders/views.py:43`) persiste o pedido, invalida o cache (Aula 8) e
publica o evento via `orders/mensageria/produtor.py`. Como o Django é
síncrono (WSGI), o `AIOKafkaProducer` roda num *event loop* próprio numa
thread *daemon*; a view chama a API síncrona `publicar_evento()`, que aguarda
o envio com timeout (`KAFKA_TIMEOUT_PUBLICACAO`, 5s).

**Degradação graciosa** (mesma política do cache na Aula 8): se o broker
estiver em baixo, o pedido continua criado, o log marca
`acao=publicar status=falha` e o produtor é reiniciado na tentativa seguinte.

### Consumidor (worker)

*Serviço próprio no Compose*, que corre
`python manage.py consumir_pedido_criado`
(`orders/management/commands/consumir_pedido_criado.py`):

1. consome `pedidos.criado` no grupo `synapseshop-pedidos-criado` com
   **commit manual** (após processar) → semântica **pelo menos uma vez**;
2. valida o contrato e reserva a chave de idempotência no Redis;
3. persiste o resultado no repositório: preenche `Order.evento_criado_em`
   (migração `orders/0002`);
4. confirma o offset — ou repete com *backoff*, ou despacha para a DLQ.

### Política de idempotência

| Regra | Valor |
|---|---|
| Chave | `idempotency_key` = `pedido:{pedido_id}` (chave de negócio) |
| Chave física no Redis | `synapseshop:1:idempotency:pedido_criado:pedido:{id}` |
| Mecanismo | `cache.add()` → Redis `SET NX EX` **atómico** (primeiro ganha) |
| TTL | `IDEMPOTENCY_TTL` = 24h (86400s) |
| Duplicado detectado | log `dedupe=duplicada`, mensagem confirmada **sem** reprocessar |
| Redis em baixo | `RedisError` é tratado como falha de processamento (reentrega), nunca como "processado" |

Se a reserva existe mas o pedido ainda não tem `evento_criado_em`, a tentativa
anterior falhou *entre* reservar e gravar — nesse caso o *worker* continua o
processamento em vez de descartar a mensagem (evita perder atualizações por
falha no meio do caminho).

### Reentrega e *backoff*

| Parâmetro | Env | Padrão |
|---|---|---|
| Máximo de tentativas | `MENSAGERIA_TENTATIVAS` | `5` |
| *Backoff* base | `MENSAGERIA_BACKOFF_BASE` | `0.5s` |
| *Backoff* máximo | `MENSAGERIA_BACKOFF_MAXIMO` | `8s` |
| Fórmula | — | `min(BASE * 2**(n-1), MAX)` → 0.5, 1, 2, 4 s |

Cada falha gera `acao=consumir status=falha tentativa=n/5 proxima_reentrega_em=...`.
Esgotadas as tentativas, a mensagem vai para a DLQ e o offset é confirmado
(mensagens "envenenadas" não bloqueiam a fila).

### Estratégia de DLQ

- **Tópico:** `pedidos.criado.dlq` (auto-criado).
- **Payload:** a mensagem original, byte a byte, para reprocessamento manual.
- **Headers de diagnóstico:** `x-error`, `x-tentativas`, `x-topico-original`,
  `x-particao`, `x-offset`.
- **Offset:** confirmado só depois do envio para a DLQ — se o envio falhar, a
  mensagem fica por confirmar e o worker (com `restart: on-failure`)
  reprocessa-a no arranque.
- **Inspeção:**

```bash
docker exec synapseshop-redpanda rpk topic consume pedidos.criado.dlq \
  -n 1 -F '%kv{key} %v\n'
```

### Fluxo completo validado

```bash
docker compose up -d --build

curl -s -X POST http://127.0.0.1:8000/api/v1/pedidos/ \
  -H "Content-Type: application/json" -d '{"user_id": 7, "total": "129.90"}'

docker compose logs worker | grep acao=
# api:     evento=PedidoCriado acao=publicar status=sucesso topico=pedidos.criado duracao_ms=2.1
# worker:  evento=PedidoCriado acao=consumir status=sucesso desfecho=novo tentativas=1 duracao_ms=8.4 latencia_ms=152.7
# worker:  evento=PedidoCriado pedido_id=1 ... acao=processar dedupe=novo status=persistido
```

**Duplicado** (mesma chave de negócio):

```bash
docker compose exec -w /app/api/v1/products api \
  python /app/scripts/simular_duplicado.py --pedido-id 1
# worker: evento=PedidoCriado ... acao=processar dedupe=duplicada
```

**Falha forçada → DLQ** (5 tentativas com *backoff*, depois DLQ):

```bash
MENSAGERIA_FORCAR_FALHA=1 docker compose up -d worker   # ou adicione a env ao compose
curl -s -X POST http://127.0.0.1:8000/api/v1/pedidos/ \
  -H "Content-Type: application/json" -d '{"user_id": 8, "total": "55.00"}'
docker compose logs worker | grep -E "status=falha|status=dlq"
docker exec synapseshop-redpanda rpk topic consume pedidos.criado.dlq -n 1
```

### Métricas nos logs

Logger `orders.mensageria` (formato *key=value*), com
`MESSAGING_LOG_LEVEL=INFO` por omissão:

| Campo | Significado |
|---|---|
| `duracao_ms` (publicar) | Montagem + envio do evento ao Kafka |
| `duracao_ms` (consumir) | Processamento completo, incluindo reentregas |
| `latencia_ms` | `occurred_at` → consumação (inclui tempo na fila) |
| `tentativas` | Tentativas usadas no processamento |

Análise:

```bash
docker compose logs worker | grep "acao=consumir"
docker compose logs api     | grep "acao=publicar"
```

Exemplo de amostra (logs da validação desta aula — os valores por execução
variam, tal como no Aula 8):

| cenário | `duracao_ms` (consume) | `latencia_ms` | desfecho |
|---|---|---|---|
| caminho normal, 1.ª tentativa | 6–15 | ~100–250 | `desfecho=novo` |
| duplicado | 3–8 | ~300+ | `desfecho=duplicada` |
| falha forçada | 7500 (4 *backoffs*) | ~7600 | `status=dlq` |

### Variáveis de ambiente da Aula 9

| Variável | Padrão | Uso |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9094` (fora do Compose) / `redpanda:9092` | Brokers |
| `IDEMPOTENCY_TTL` | `86400` | TTL do dedupe (s) |
| `MENSAGERIA_TENTATIVAS` | `5` | Tentativas antes da DLQ |
| `MENSAGERIA_BACKOFF_BASE` | `0.5` | *Backoff* exponencial (s) |
| `MENSAGERIA_BACKOFF_MAXIMO` | `8` | Teto do *backoff* (s) |
| `MENSAGERIA_FORCAR_FALHA` | `0` | `1` simula falha permanente (validação da DLQ) |
| `KAFKA_TIMEOUT_LIGACAO` / `KAFKA_TIMEOUT_PUBLICACAO` | `5` | Timeouts de ligação/publicação (s) |
| `MESSAGING_LOG_LEVEL` | `INFO` | Nível do logger `orders.mensageria` |

O `redpanda` expõe `9094` (Kafka, externo), `9092` (interno, para `api` e
`worker`) e `9644` (admin, para o healthcheck `rpk cluster health`).

### Escopo da Aula 9

Apenas a infraestrutura de mensageria do fluxo `PedidoCriado`. **Não** foram
antecipados: testes automatizados, pipelines CI/CD, componentes de IA/RAG,
pagamento/notificação (Aula 11), `OrderItem` ou novos microsserviços.

---

## Aula 10 — Kafka: partições, offset, streams e métricas

### Objetivo

Aprofundar o uso do Kafka no fluxo `PedidoCriado` entregue na Aula 9:
configuração explícita de tópicos (partições e retenção), paralelismo de
consumo com vários *workers* no mesmo grupo, semântica de offset, leitura de
*streams* e a coleta de métricas de latência/throughput com os trade-offs do
mecanismo de dedupe.

### Tópicos, partições e retenção

A configuração é centralizada em `orders/mensageria/topicos.py` e garantida no
arranque do *worker* (e por `python manage.py garantir_topicos`):
`pedidos.criado` é criado com **3 partições** (paralelismo de consumo, chave =
`idempotency_key` → o mesmo pedido vai sempre para a mesma partição) e a DLQ
com **1 partição**. A retenção é das DLQ sendo longa e do tópico principal
curta (Kafka como fila operacional, não como armazenamento de histórico).

| Tópico | Partições | Retenção | Env |
|---|---|---|---|
| `pedidos.criado` | 3 (`KAFKA_PARTICOES`) | 1h (`KAFKA_RETENCAO_HORAS`) | `retention.ms` + `cleanup.policy=delete` |
| `pedidos.criado.dlq` | 1 | 7 dias (`KAFKA_RETENCAO_DLQ_HORAS`) | idem |

Se o tópico já existir com menos partições, `garantir_topicos` **aumenta** as
partições (o Kafka não reduz) e apenas informa sobre a retenção:

```bash
docker exec synapseshop-redpanda rpk topic describe pedidos.criado
docker exec synapseshop-redpanda rpk topic describe pedidos.criado.dlq
```

### Semântica de offset

- `enable_auto_commit=False` + **commit manual** apenas após processar (ou
  encaminhar para DLQ) → pelo menos uma vez.
- `auto_offset_reset=earliest` → em grupo novo (ou após retenção expirar), a
  leitura recomeça do início do tópico.
- Commit por mensagem; ao confirmar, o *worker* avança o offset da partição.
  Um crash antes do commit devolve a mensagem no rebalance/rearranque — e a
  idempotência (Redis `SET NX EX`) bloqueia o reprocessamento.
- Os logs `acao=consumir` expõem `particao`, `offset` e `worker_id` para
  rastreio por partição.

### Múltiplos consumidores (paralelismo por partições)

Vários *workers* no mesmo grupo repartem as partições automaticamente
(rebalance), sem alteração de código:

```bash
docker compose up -d --scale worker=3     # 3 workers, 1 partição cada
```

O serviço `worker` não usa `container_name` no compose (necessário para o
`--scale` funcionar). Cada instância loga `worker_id=<hostname>:<pid>` (o
`hostname` do container é único; o PID PODE repetir-se entre containers porque
cada um tem o seu próprio namespace).

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/pedidos/ \
  -H "Content-Type: application/json" -d '{"user_id": 1, "total": "10.00"}'
# ... repetir para gerar carga
docker compose logs worker | grep "acao=consumir"
```

Os logs mostram a distribuição: cada `worker_id` processa partições diferentes
e a mesma `idempotency_key` cai sempre na mesma partição (ordem por partição
preservada). Para ver o rebalance, derrube um *worker* e observe os restantes
assumirem as suas partições:

```bash
docker compose stop worker           # escala volta a N-1
docker compose logs worker | grep -E "particao|worker_id"
docker compose up -d worker          # volta ao N
```

### Streams

Um tópico Kafka é um *log* continuo: vários grupos podem ler o mesmo stream
independentemente. `scripts/estatisticas_stream.py` é um segundo consumidor
(grupo `synapseshop-estatisticas-stream`, `auto_offset_reset=earliest`) que lê
do início sem afetar os *workers* e agrega contagens por partição e a latência
de leitura — uma leitura de *stream* leve, sem Kafka Streams (Java):

```bash
api/v1/products/.venv/Scripts/python scripts/estatisticas_stream.py --limite 50
api/v1/products/.venv/Scripts/python scripts/estatisticas_stream.py --duracao 5
```

Exemplo de saída:

```
topico=pedidos.criado lidos=80 por_particao={'particao_0': 51, 'particao_1': 29}
latencia_ms min=74724.64 media=725981.55 p95=4578555.11 max=4798239.83
```

(As latências históricas correspondem a eventos antigos ainda retidos no tópico;
com `--duracao 5` a janela é um slice do *log* atual.)

### Métricas de latência e throughput

`orders/mensageria/metricas.py` acumula no Redis (chaves
`synapseshop:1:mensageria:metricas:*`, sem TTL) contadores e somas do fluxo:
publicações (sucesso/falha), consumos, duplicados, DLQ e os totais de
`duracao_ms`/`latencia_ms`. Expostos em:

```bash
curl -s http://127.0.0.1:8000/api/v1/pedidos/metricas-mensageria/
```

```json
{"produtor":{"publicacoes":100,"publicacoes_falhas":0,"publicacoes_total":100,
  "tempo_medio_ms":3.13,"tempo_total_ms":312.7},
 "consumidor":{"consumos":100,"duplicados":0,"dlq":0,"falha_percentual":0.0,
  "duracao_media_ms":21.39,"latencia_media_ms":32.01,
  "duracao_total_ms":2139.0,"latencia_total_ms":3200.8}}
```

O `produtor.tempo_medio_ms` mede apenas o envio ao Kafka (não o `POST` inteiro);
a latência de publicação HTTP é medida pelo benchmark.

**Benchmark** (`scripts/medidor_fluxo.py`): cria `--pedidos` pedidos via
`POST` com `--concorrencia` threads, mede a latência de publicação e a vazão do
produtor, e aguarda o consumo contando os deltas das métricas (vazão do
consumidor + latência ponta-a-ponta média):

```bash
api/v1/products/.venv/Scripts/python scripts/medidor_fluxo.py --pedidos 100 --concorrencia 10
```

| etapa | requisições | duração (s) | média (ms) | p95 (ms) | RPS |
|---|---|---|---|---|---|
| produtor (`POST /pedidos`, 10 threads) | 100 | 3.78 | 359.2 | 501.4 | 26.4 |
| consumidor (worker, 3 partições) | 100 | 3.90 | 21.4 | — | 25.6 |

Resultados da validação desta aula (3 *workers*, 3 partições):

- **Variável e dependente da carga/ambiente:** como nas Aulas 8–9, os números
  de uma execução servem de referência, não de constante. A publicação é o
  gargalo (o `POST` inclui persistência no banco + invalidação de cache +
  envio ao Kafka com ack), por isso a latência média do produtor cresce com a
  concorrência. Com `--concorrencia 4` cai para ~119 ms média / 139 ms p95
  (RPS ~32); com `--concorrencia 20` tende ao limite dos 2 *workers* do
  gunicorn (síncronos) e sobe para ~780 ms — a fila do servidor, não o Kafka.
- **Contadores exatos sob paralelismo:** o acumulador Redis usa `INCRBY`
  atómico com criação via `SET NX` (só um processo cria a chave; os que
  perderem a corrida somam por cima) — sob 3 consumidores o `consumos` bate
  com o número de eventos efetivamente lidos (LAG=0 via `rpk group describe`),
  sem perdas nem duplicações por corrida.
- **Trade-off do dedupe:** cada consumo paga um `SET NX EX` no Redis antes da
  gravação — ~1–3 ms extra por evento, que mantém o throughput no mesmo
  patamar (paralelo nas partições) e evita duplicatas a um custo baixo vs.
  reprocessamento. O custo aparece em `duracao_media_ms` do consumidor
  (~21 ms no benchmark, incluindo gravação no Postgres).
- **Latência ponta-a-ponta** média (`publicação → consumo`) de ~32 ms nesta
  execução. Num pedido pouco simultâneo fica perto do `duracao_ms` de consumo;
  sob carga cresce pelo *batch* do consumidor.
- **Throughput** escala com as partições: 3 *workers/3* partições processam
  em paralelo, mas 3 partições/1 *worker* processam em série dentro da mesma
  partição (a chave garante ordem por pedido).
- **Rebalance sem perda:** com `--scale worker=2` um dos workers ficou com as
  partições 0 e 2 e o outro com a 1; os eventos migraram sem perda nem
  duplicação (idempotência cobriu qualquer reprocessamento).

Análise a partir de logs:

```bash
docker compose logs worker | grep "acao=consumir"     # latencia_ms e duracao_ms por evento
docker compose logs api     | grep "acao=publicar"    # duracao_ms de publicação
```

### Variáveis de ambiente da Aula 10

| Variável | Padrão | Uso |
|---|---|---|
| `KAFKA_PARTICOES` | `3` | Partições de `pedidos.criado` |
| `KAFKA_RETENCAO_HORAS` | `1` | Retenção de `pedidos.criado` (horas) |
| `KAFKA_RETENCAO_DLQ_HORAS` | `168` | Retenção da DLQ (7 dias) |

As variáveis da Aula 9 continuam válidas (`MENSAGERIA_TENTATIVAS`, `BACKOFF_*`,
`IDEMPOTENCY_TTL`, `MENSAGERIA_FORCAR_FALHA`, etc.).

### Escopo da Aula 10

Apenas aprofundamento da mensageria Kafka do fluxo `PedidoCriado`. **Não**
foram antecipados: testes automatizados, pipelines CI/CD, componentes de
IA/RAG, dashboards (ex.: Streamlit), pagamento/notificação (Aula 11),
`OrderItem` ou novos microsserviços.

## Aula 11 — Desafio Mão na Massa: Núcleo do Mini-Backend

Consolidação do fluxo de negócio mínimo da loja: **criar pedido → simular
pagamento → notificar**, usando o que foi construído nas Aulas 8–10 (cache
as-is `Redis` + mensageria Kafka/Redpanda) com um novo worker e um novo
tópico.

### Fluxo operacional

```
POST /pedidos/  ──►  persistir + invalidar cache  ──►  pedidos.criado
                                                        │
                                                        ▼
                                  worker consumir_pedido_criado  (Aula 9/10)

POST /pedidos/{id}/pagar/  ──►  pending→paid (ou recusa)  ──►  pedidos.pagamento
                                                                   │
                                                                   ▼
                              worker-notificacoes consumir_pagamento
                                                      │
                                                      ▼
                               notificação simulada (log acao=notificar)
```

### Novos serviços e endpoints

Tabela de endpoints da Aula 11:

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Healthcheck: verifica db (obrigatório), redis e kafka (degradação → `200 degraded`; db fora → `503`) |
| `POST` | `/api/v1/pedidos/{id}/pagar/` | Simula o pagamento (body `{"aprovado": true/false}`) |
| `GET` | `/api/v1/pedidos/{id}/detalhes/` | Detalhe do pedido (cache-aside, refletindo o novo estado) |
| `GET` | `/api/v1/pedidos/metricas-mensageria/` | Métricas, agora com bloco `notificacoes` |

Comportamento do `pagar`:

- `aprovado=true` (padrão): transição `pending → paid`, invalidação do cache e
  publicação de `PagamentoSimulado` → **200**;
- `aprovado=false`: o pedido permanece `pending`, o evento é publicado na mesma
  (a notificação de recusa também é enviada) → **402**;
- pedido não `pending` → **409**; payload com campos desconhecidos ou inválidos →
  **400**; pedido inexistente → **404**.

Novo serviço no `docker-compose.yml`:

```yaml
worker-notificacoes:   # command: python manage.py consumir_pagamento
  build: .
  depends_on: [db, redis, redpanda]  # healthchecks
  restart: on-failure
```

O `api` ganhou `healthcheck` explícito sobre `/health` (o `Dockerfile`
também passou a apontar o `HEALTHCHECK` da imagem para `/health`); os workers
(`worker` e `worker-notificacoes`) não servem HTTP e desativam o healthcheck da
imagem (`healthcheck: disable`), corrigindo o estado `unhealthy` que exibiam
desde as Aulas 9–10.

### Evento `PagamentoSimulado` e tópicos

Contrato em `orders/mensageria/contrato.py`:

```json
{
  "event_id": "…uuid…",
  "event_type": "PagamentoSimulado",
  "occurred_at": "2026-10-08T01:42:27+00:00",
  "idempotency_key": "pagamento:771",
  "payload": {
    "pedido_id": 771,
    "user_id": 21,
    "total": "99.90",
    "aprovado": true,
    "status": "paid"
  }
}
```

Novos tópicos (definidos/garantidos em `orders/mensageria/topicos.py`):

| Tópico | Partições | Retenção |
|---|---|---|
| `pedidos.pagamento` | `KAFKA_PARTICOES` (3) | `KAFKA_RETENCAO_HORAS` (1h) |
| `pedidos.pagamento.dlq` | 1 | `KAFKA_RETENCAO_DLQ_HORAS` (168h) |

O consumer mantém o ciclo completo da Aula 9: commit manual (pelo menos uma
vez), dedupe no Redis com namespace próprio
(`idempotency:pagamento_simulado:pagamento:{id}`), retry com backoff
exponencial (`MENSAGERIA_TENTATIVAS`), DLQ com headers `x-error`/`x-offset`, e
marcador `…:feito:` que distingue um duplicado real de uma falha entre a
reserva e a notificação.

### Validação manual (fluxo completo)

```bash
docker compose up --build -d

# 1) healthcheck
curl -s http://127.0.0.1:8000/health
# {"status":"ok","app":"synapseshop-api","db":"ok","redis":"ok","kafka":"ok"}

# 2) criar pedido
curl -s -X POST http://127.0.0.1:8000/api/v1/pedidos/ \
  -H "Content-Type: application/json" -d '{"user_id": 7, "total": "129.90"}'

# 3) simular pagamento aprovado
curl -s -X POST http://127.0.0.1:8000/api/v1/pedidos/771/pagar/ \
  -H "Content-Type: application/json" -d '{"aprovado": true}'
# 200 {"pedido_id":771,"status":"paid","aprovado":true,"evento_publicado":true}

# 4) repetir o pagamento -> 409; recusar outro pedido -> 402

# 5) notificação no worker
docker compose logs worker-notificacoes | grep "acao=notificar"
# evento=PagamentoSimulado acao=notificar canal=email resultado=aprovado ...
```

Logs observados nesta validação (api → worker-notificacoes):

```bash
# api
docker compose logs api | grep PagamentoSimulado
# evento=PagamentoSimulado acao=publicar status=sucesso topico=pedidos.pagamento
#   pedido_id=771 chave_idempotencia=pagamento:771 duracao_ms=2.2

# worker-notificacoes
docker compose logs worker-notificacoes | grep -E "notificar|consumir"
# evento=PagamentoSimulado pedido_id=771 ... acao=notificar canal=email
#   resultado=aprovado status=paid
# evento=PagamentoSimulado acao=consumir status=sucesso desfecho=novo
#   tentativas=1 duracao_ms=52.5 latencia_ms=55.2 particao=2 offset=0
```

Métricas (bloco `notificacoes` novo):

```bash
curl -s http://127.0.0.1:8000/api/v1/pedidos/metricas-mensageria/
# "notificacoes": {"total": 2, "aprovados": 1, "recusados": 1}
```

Alternativamente, inspecionar o tópico com `rpk topic consume pedidos.pagamento`.

### Variáveis de ambiente da Aula 11

Reutiliza as variáveis das Aulas 8–10 (`REDIS_URL`, `KAFKA_BOOTSTRAP_SERVERS`,
`MENSAGERIA_TENTATIVAS`, `BACKOFF_*`, `MENSAGERIA_FORCAR_FALHA`,
`IDEMPOTENCY_TTL`…). Nova: `HEALTH_TIMEOUT_KAFKA` (padrão `1` s) — timeout do
teste TCP de alcancabilidade do broker em `/health`.

### Escopo da Aula 11

Implementado apenas o núcleo do mini-backend (pedido → pagamento simulado →
notificação). **Não** foram antecipados: testes automatizados, pipelines
CI/CD, dashboards/extração de dados (próximas aulas), `OrderItem`,
`users-service` na orquestração, autenticação de pagamento ou envio real de
notificações (a notificação é simulada por log).
