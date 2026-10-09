# Checklist do Integrador Externo — SynapseShop API

Guia de consumo da API por terceiros. Complementa o contrato
[`docs/openapi.yaml`](openapi.yaml), servido em `/api/v1/schema/` e navegável
em `/api/v1/docs/` (Swagger UI) e `/api/v1/redoc/` (ReDoc).

## 1. URLs de ambiente

| Ambiente | Base URL | Observações |
|---|---|---|
| Local | `http://127.0.0.1:8000` | `docker compose up`; Swagger em `/api/v1/docs/` |
| Homologação | `https://api.synapseshop.local` | Exemplo; substituir pelo domínio real |

Prefixo versionado de todos os recursos: `/api/v1/`.

- [ ] Confirme a *base URL* do ambiente antes de importar a coleção.
- [ ] Verifique a disponibilidade em `GET /health` (200 = operacional,
  503 = base de dados indisponível, `degraded` = Redis/Kafka opcionais fora).

## 2. Autenticação

- Esquema documentado: `Authorization: Bearer <token>` (`bearerAuth`, JWT).
- **Estado atual:** a API aceita pedidos anónimos; o cabeçalho é aceito e
  reservado para a evolução da autenticação.
- [ ] Não inclua credenciais reais no ficheiro de ambiente versionado; use a
  variável `token` do environment (`type: secret`).
- [ ] Em caso de `401`, renove o token antes de repetir o pedido.

## 3. Cabeçalhos obrigatórios e opcionais

| Cabeçalho | Obrigatório | Descrição |
|---|---|---|
| `Authorization` | Não (evol.) | `Bearer <token>` |
| `Idempotency-Key` | Recomendado em `POST` | Evita criação duplicada em retentativas |
| `X-Trace-Id` | Opcional | Correlação; se ausente, a API gera e devolve o valor |

- [ ] Propague o `X-Trace-Id` devolvido na resposta ao reportar incidentes.

## 4. Convenções de consulta

- **Paginação (opcional):** `?page=<n>&limit=<n>`. Sem parâmetros, a coleção
  inteira é devolvida como lista; com eles, a resposta passa a
  `{ count, next, previous, nextCursor, results }` (máximo de 100 itens).
- **Filtros:** por igualdade em campos declarados — `?status=pending`
  (pedidos), `?categoria=<id>` (itens), `?user_id=<id>` (pedidos).
- **Ordenação:** `?sort=campo:asc|desc` — ex.: `?sort=createdAt:desc`,
  `?sort=preco:asc`.
- [ ] Não assuma ordenação implícita: peça `sort` explicitamente quando a
  ordem for relevante.

## 5. Erros

Erros seguem o envelope inspirado na RFC 7807:

```json
{
  "type": "about:blank",
  "title": "Requisição inválida",
  "status": 400,
  "detail": "Requisição inválida",
  "instance": "/api/v1/pedidos/",
  "errors": { "total": ["O total do pedido deve ser um valor não negativo."] }
}
```

| Código | Significado |
|---|---|
| `200` / `201` / `204` | Sucesso (leituras/escritas/exclusão) |
| `400` | Payload inválido (validação por campo em `errors`) |
| `402` | Pagamento recusado |
| `404` | Recurso inexistente |
| `409` | Estado incompatível (ex.: pagar pedido não pendente) |
| `500` / `503` | Erro interno / dependência obrigatória indisponível |

- [ ] Trate `4xx` como erro de cliente (não repetir sem corrigir a requisição).
- [ ] Faça *backoff* exponencial em `429`/`5xx`.

## 6. Limites de utilização (*rate limits*)

- A API do mini-backend **não aplica** limite de requisições nesta fase.
- Recomendação para integradores: máximo de 5 req/s por cliente e uso de
  `Idempotency-Key` em escritas.
- [ ] Aguarde a publicação de um cabeçalho `RateLimit-*` antes de assumir
  quotas rígidas.

## 7. Política de alterações de versão

- Mudanças **compatíveis** (novos campos opcionais, novos endpoints) entram sem
  alterar o prefixo `/api/v1/`.
- Mudanças **incompatíveis** (remoção/renomeação de campos, novas validações
  obrigatórias) originam `/api/v2/`, com `/api/v1/` mantido por um período de
  transição.
- Histórico de alterações: ver [`CHANGELOG.md`](../CHANGELOG.md).
- [ ] Assine o acompanhamento do `CHANGELOG.md` antes de subir de versão.

## 8. Artefactos de apoio

- [ ] Coleção Postman: `postman/collections/SynapseShop API.postman_collection.json`.
- [ ] Environment Postman: `postman/environments/SynapseShop Local.postman_environment.json`.
- [ ] Contrato OpenAPI: `docs/openapi.yaml` (validado com Spectral).
