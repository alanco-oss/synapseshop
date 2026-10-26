## Aula 13 — Documentação OpenAPI/Swagger e Postman/Insomnia

### Objetivo

Padronizar, enriquecer e publicar a documentação da API do SynapseShop: o
contrato OpenAPI 3.0.3, as interfaces interativas Swagger UI e ReDoc, a coleção
Postman com *environment* e a Checklist do Integrador Externo. Escopo restrito
aos endpoints já existentes — sem antecipar IA, mensageria avançada ou
dashboards (aulas posteriores).

### Artefactos

| Artefacto | Caminho |
|---|---|
| Contrato OpenAPI | `docs/openapi.yaml` |
| Regras de lint | `.spectral.yaml` |
| Checklist do Integrador | `docs/checklist_integrador_externo.md` |
| Histórico de alterações | `CHANGELOG.md` |
| Coleção Postman | `postman/collections/SynapseShop API.postman_collection.json` |
| Environment Postman | `postman/environments/SynapseShop Local.postman_environment.json` |

### Documentação interativa

```bash
docker compose up -d api
# navegador:
#   http://127.0.0.1:8000/api/v1/docs/     -> Swagger UI
#   http://127.0.0.1:8000/api/v1/redoc/    -> ReDoc
#   http://127.0.0.1:8000/api/v1/schema/   -> OpenAPI (YAML)
```

As páginas carregam Swagger UI/ReDoc por CDN e consomem o mesmo
`docs/openapi.yaml` servido em `/api/v1/schema/` (a rota é localizada mesmo
dentro do contêiner, onde o ficheiro fica em `/app/docs/openapi.yaml`).

### Convenções documentadas

- **Rotas:** recursos no plural sob o prefixo versionado `/api/v1/`.
- **Paginação (opcional):** `?page=<n>&limit=<n>`. Sem os parâmetros, a coleção
  é devolvida como lista simples (contrato preservado); com eles, o envelope é
  `{ count, next, previous, nextCursor, results }`.
- **Filtros:** `?status=` (pedidos), `?categoria=` (itens), `?user_id=`
  (pedidos).
- **Ordenação:** `?sort=campo:asc|desc` (`?sort=createdAt:desc`,
  `?sort=preco:asc`).
- **Cabeçalhos:** `Authorization: Bearer <token>` (reservado), `Idempotency-Key`
  (recomendado em `POST`) e `X-Trace-Id` (gerado e devolvido se ausente).

As convenções vivem em `products/api_conventions.py` e o `X-Trace-Id` em
`products/middleware.py`. A implementação é retrocompatível: sem parâmetros de
consulta, o comportamento anterior à Aula 13 mantém-se (inclusive o cache-aside
da listagem de pedidos).

### Erros padronizados (RFC 7807)

`products/exceptions.py` normaliza os erros no envelope
`type`/`title`/`status`/`detail`/`instance`, replicando os erros de validação
por campo em `errors` **e** no nível de topo (compatibilidade com clientes
anteriores):

```json
{
  "type": "about:blank",
  "title": "Requisição inválida",
  "status": 400,
  "detail": "Requisição inválida",
  "instance": "/api/v1/pedidos/",
  "errors": { "total": ["O total do pedido deve ser um valor não negativo."] },
  "total": ["O total do pedido deve ser um valor não negativo."]
}
```

### Validação estática (lint)

```bash
npx --yes @stoplight/spectral-cli lint docs/openapi.yaml
# No results with a severity of 'error' found!
```

O ruleset (`.spectral.yaml`) estende `spectral:oas`, exige `operationId`
único, tags definidas, resposta de sucesso e parâmetros de rota válidos. As
regras desligadas (`path-keys-no-trailing-slash`, `operation-description`,
`info-contact`/`info-license`, `tag-description`) estão justificadas no próprio
ficheiro.

### Coleção Postman / Insomnia

A coleção traz pastas `Health`, `Categorias`, `Itens`, `Pedidos` e
`Documentação`, com variáveis `baseUrl`, `token`, `traceId`, `idempotencyKey`,
`cat_id`, `item_id` e `pedido_id`. O environment `SynapseShop Local` guarda o
`token` como `secret`. Há exemplos gravados de sucesso (200/201) e erro
(400/402/409), incluindo o envelope paginado.

### Resultado (DoD da Aula 13)

| Item | Estado |
|---|---|
| OpenAPI com schemas de resposta e `ErrorSchema`/RFC 7807 | ✅ `docs/openapi.yaml` |
| Paginação, filtros, ordenação e cabeçalhos documentados | ✅ |
| Lint estático sem erros | ✅ Spectral |
| Swagger UI e ReDoc funcionais | ✅ `/api/v1/docs/`, `/api/v1/redoc/` |
| Coleção Postman com *environment* e exemplos | ✅ |
| `docs/` versionada + `CHANGELOG.md` | ✅ |
| Checklist do Integrador Externo | ✅ `docs/checklist_integrador_externo.md` |
| `PROMPTS.md` atualizado | ✅ |
| `docker compose up` sem dependências de aulas futuras | ✅ |

### Escopo da Aula 13

Documentação e padronização dos contratos existentes (`catalog`, `orders`,
`products`). **Não** foram antecipados: inteligência artificial, mensageria
avançada, dashboards analíticos, autenticação efetiva (o `bearerAuth` é apenas
documentado) ou *rate limiting* em runtime.
