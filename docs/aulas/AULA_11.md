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

---
