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
