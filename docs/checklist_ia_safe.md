# Checklist "IA-safe" — Revisão de Código Gerado por IA

Guia obrigatório aplicado a todo código sugerido por assistentes de IA no
SynapseShop. Antes de incorporar qualquer trecho, confirme **todos** os pontos
abaixo para garantir que o código é seguro, tipado e aderente à spec ativa.

## 1. Imports e Dependências
- [ ] Cada import é usado de fato (sem imports órfãos).
- [ ] Não há bibliotecas de escopo futuro (ex.: Redis, JWT, FastAPI) na spec atual.
- [ ] As versões estão pinadas em `requirements.txt` e reproduzíveis via
      `pip install -r requirements.txt`.
- [ ] Nenhuma dependência duplicada ou reinvenção do que já existe no framework.

## 2. Modelagem e Tipos de Dados
- [ ] Campos do `Model` têm tipos coerentes com o domínio (Decimal para preço,
      inteiro positivo para estoque, etc.).
- [ ] `null`/`blank`/`default` estão explícitos onde a regra de negócio exige.
- [ ] O `ModelSerializer` deriva de `ModelSerializer` e expõe exatamente os
      campos transacionais do recurso.
- [ ] O payload aceito/rejeitado reflete a tipagem declarada (ex.: `preco`
      aceita string decimal ou número, nunca valor alfanumérico).

## 3. Validações Customizadas
- [ ] Toda regra de negócio que extrapola o ORM tem validação explícita
      (`validate_<campo>`, `validators` ou validação de serializer).
- [ ] Payload inválido responde com `400 Bad Request`, sem exceções vazadas
      (traceback) ao cliente.
- [ ] Não há validação somente no cliente: a API valida de forma independente.

## 4. ViewSets, Roteamento e Status HTTP
- [ ] O `ViewSet` herda de `ModelViewSet` com `queryset` e `serializer_class`.
- [ ] Rotas registradas em `DefaultRouter` sob prefixo versionado (`/api/v1/`),
      sem vazamento de rotas futuras.
- [ ] Status codes padrão verificados:
  - `200 OK` — listagem/recuperação/atualização
  - `201 Created` — criação
  - `204 No Content` — exclusão
  - `400 Bad Request` — payload inválido
  - `404 Not Found` — recurso inexistente

## 5. Segurança e Ambiente
- [ ] Nenhuma credencial, `SECRET_KEY` de produção ou variável sensível exposta
      no código versionado.
- [ ] O contêiner roda como usuário não-root e o banco local (`*.sqlite3`)
      não é embarcado na imagem.
- [ ] Escopo restrito à spec da aula atual (sem antecipação de features).

---

### Aplicação na Aula 4 (DRF CRUD)
Revisado e comprovado em `/api/v1/categories/` e `/api/v1/items/` (app `catalog`):

- `GET` → `200 OK` de lista vazia; `GET /:id/` → `200 OK`
- `POST` (payload válido) → `201 Created` com `id`
- `PUT` / `PATCH` → `200 OK` com campos atualizados
- `DELETE` → `204 No Content`; segundo `GET` no mesmo id → `404 Not Found`
- `POST` com `preco: "-5"` → `400 Bad Request` (validação customizada
  `validate_preco` no `ItemSerializer`)
- `POST` sem `nome` → `400 Bad Request` (campo obrigatório)
- `POST` com `categoria` inexistente → `400 Bad Request`
  (chave estrangeira inválida)