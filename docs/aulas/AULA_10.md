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
