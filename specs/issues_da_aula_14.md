# Issues a criar — pendências da Aula 14

Pendências identificadas durante a Aula 14 (assistente de IA), prontas a colar
no GitHub (`gh issue create` ou interface web). Uma secção por issue.

---

## 1. Métricas persistentes do circuit breaker

**Título:** `feat: métricas e persistência do circuit breaker (Redis)`

**Corpo:**

O `circuit_breaker` do app `assist` é mantido em memória por processo: o estado
(closed/open/half-open), a contagem de falhas e o registo de aberturas
reiniciam quando o worker/API reinicia.

**A fazer:**

- [ ] Endpoint de métricas do circuito (estado, falhas correntes, aberturas
      acumuladas, última abertura) no formato das métricas das Aulas 8–10.
- [ ] Persistir estado e contadores no Redis (padrão já usado em cache-aside).
- [ ] Decidir o comportamento com múltiplas réplicas (estado partilhado vs.
      `local-first` com TTL).
- [ ] Alertas/logs de transição `open` (aviso distinto).

---

## 2. Cache de respostas do assistente

**Título:** `feat: cache de respostas do assistente por chave de prompt`

**Corpo:**

Perguntas idênticas (mesmo `mode`, `logs` redigido, `temperature` e
`max_tokens`) produzem repetidamente o mesmo consumo de tokens no provedor —
custo e latência desnecessários.

**A fazer:**

- [ ] Chave de cache normalizada a partir do `logs` **redigido** (+ `mode`,
      `temperature`, `max_tokens`) para nunca guardar PII.
- [ ] TTL configurável (`ASSIST`, ex.: 15 min) e invalidação por troca de
      `LLM_MODEL`.
- [ ] `meta` deve indicar `cache_hit` e, em hit, reutilizar
      `tokens_prompt`/`tokens_output` do primeiro pedido.

---

## 3. Guardrails e validação de conteúdo

**Título:** `feat: guardrails na saída e no uso do assistente`

**Corpo:**

A resposta do provedor é devolvida ao cliente sem qualquer pós-filtro. Não há
registo de uso por utilizador nem bloqueio de conteúdo sensível _gerado_.

**A fazer:**

- [ ] Filtro de saída (negação de PII gerada, classificação básica) antes de
      devolver `answer`.
- [ ] Bloqueio/limite por origem (rate limit do assistente além do global).
- [ ] Registo de utilização (utilizador → nº de pedidos/tokens por janela) sem
      guardar os textos originais.

---

## 4. Testes de integração com o provedor (contract tests)

**Título:** `test: contract tests com o provedor de LLM`

**Corpo:**

A suíte da Aula 14 usa um provedor fake; a adaptação ao contrato real
(OpenAI-compatible) não é verificada — campos de resposta, códigos de erro e
`usage` assumidos podem divergir.

**A fazer:**

- [ ] Testes de contrato opcionais (`LLM_INTEGRATION=1`), com `LLM_API_KEY`
      injetada seguramente ou contra um servidor *mock* do contrato OpenAI.
- [ ] Golden files para `usage` → `tokens_prompt`/`tokens_output`.
- [ ] Documentar a matriz de erros observáveis (400/401/408/429/5xx) no README.

---

## 5. Streaming da resposta (SSE)

**Título:** `feat: streaming (SSE) da resposta do assistente`

**Corpo:**

Respostas longas esperam o fim do provedor para devolver `answer`. Para logs
extensos, aponta-se para `Server-Sent Events` com a resposta parcial a chegar
em blocos.

**A fazer:**

- [ ] `POST /api/v1/assist/stream` (ou `?stream=true`) com `text/event-stream`.
- [ ] Manter o timeout ≤ 5 s por bloco (não por resposta completa).
- [ ] `meta.tokens_*` enviado no evento final.

---

## 6. Rotação segura de `LLM_API_KEY`

**Título:** `sec: rotação segura e gestão da LLM_API_KEY`

**Corpo:**

A chave vive na env var do serviço `api`. A rotação implica `docker compose`
+ deploy; a chave não deve aparecer em logs nem em `docker inspect`/envs.

**A fazer:**

- [ ] Leitura via secrets/vault (ex.: Docker secrets, 1Password CLI, KMS) com
      fallback a env var apenas em dev.
- [ ] `Authorization` nunca logado (inclusive em debug do `requests`).
- [ ] Documentar o processo de rotação sem *downtime*.

---

## 7. Autenticação efetiva do endpoint Assistente

**Título:** `auth: autenticar o endpoint /api/v1/assist`

**Corpo:**

`bearerAuth` está apenas documentado; qualquer cliente sem token consume o
provedor de LLM à custa da organização.

**A fazer:**

- [ ] Tornar obrigatório o token no `assist` e nos restantes `POST` de escrita.
- [ ] Distribuição de credenciais (integrador externo) — ver
      `docs/checklist_integrador_externo.md`.
- [ ] Atualizar OpenAPI/Postman quando o requisito for aceite.