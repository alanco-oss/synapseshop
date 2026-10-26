## Aula 14 — Assistente de IA com `llm_service` resiliente

Novo app `assist` (`api/v1/products/assist/`) expõe **sumarização e explicação
de logs** através de um provedor de LLM, com tolerância a falhas de rede: o
chamador vê latência máxima e estados de erro claros (400/502/503), em vez de
*timeout* silencioso no servidor.

### Objetivo

- Endpoint único `POST /api/v1/assist` (aceita também `/api/v1/assist/`)
  para resumir (`mode: summarize`) ou explicar (`mode: explain`) logs;
- `llm_service` desacopla a integração do provedor: **timeout ≤ 5 s**,
  **3 tentativas** com *backoff* exponencial + *jitter*, e **circuit breaker**
  que corta o provedor após falhas consecutivas;
- **redação de PII** (`redaction.py`): emails, CPF/CNPJ, cartões, telefones,
  IPs, tokens `Bearer` e linhas de `senha`/`segredo` saem como
  `[REDIGIDO:<tipo>]` antes de qualquer envio à rede;
- **telemetria** em logs estruturados (duração, tentativas, erro, custo
  estimado) sem textos originais, para auditoria sem vazar dados.

### Contrato

`POST /api/v1/assist` — `Content-Type: application/json`

```json
{
  "mode": "summarize",
  "logs": ["erro ao autenticar joao@empresa.com", "timeout no pagamento"],
  "temperature": 0.3,
  "max_tokens": 256
}
```

- `mode`: `summarize` | `explain` (obrigatório);
- `logs`: string ou lista de strings (obrigatório, sem vazio);
- `temperature`: 0.0–1.0 (padrão `0.3`);
- `max_tokens`: ≥ 1 (padrão `256`).

Resposta `200`:

```json
{
  "answer": "O log regista uma falha de autenticação e um timeout no pagamento.",
  "meta": { "tokens_prompt": 128, "tokens_output": 45 }
}
```

- **400** envelope RFC 7807 com erros por campo (quando `LLM_API_KEY` não
  configurada, a própria configuração devolve 503 antes de validar o body);
- **502** o provedor respondeu com erro determinístico (4xx, exceto 429);
- **503** o provedor não respondeu após as retentativas, o timeout total
  estourou, o circuito está aberto ou a chave não está configurada.

### Resiliência do `llm_service`

`llm_service.chamar_llm()` é uma cascata `call`/`_resposta_do_provedor`/

`_autenticacao`/`_falar_com_llm`. Pontos de comportamento:

| Cenário | Resultado |
|---|---|
| Timeout `.read(5)` excede | Retry (máx. `LLM_RETRIES`, 3) |
| HTTP 429/5xx / `ConnectionError` / timeout de conexão | Retry com backoff `2^t + jitter` |
| HTTP 4xx não-429 (incl. 400/401/403/404/422/408...) | Falha imediata → `ErroProvedor` → **502** |
| Retentativas esgotadas | `ServicoIndisponivel` → **503** |
| Circuito aberto (chamadas de negócio falhas) | Recusa imediata → **503** |
| `LLM_API_KEY` ausente | `ServicoIndisponivel` → **503** |

O **circuit breaker** (`circuit_breaker.py`) conta **chamadas** do serviço
(abre com `LLM_CIRCUIT_FALHAS_PARA_ABRIR`, padrão 3; fecho automático após
`LLM_CIRCUIT_TIMEOUT_ABERTO`, padrão 60 s) e a cada falha de chamada o estado é
levado a `closed`, reiniciando a contagem. Retentativas HTTP dentro da mesma
chamada **não** contam para o breaker — só a resolução final da chamada conta.

### Redação de PII

`redaction.redigir()` aplica padrões em ordem de especificidade (segredos e
`Bearer` primeiro), depois `email`, `cpf/cnpj`, `cartao`, `telefone` e `ip`.
Todo texto enviado ao provedor e todo texto registado nos logs de telemetria é
o texto redigido — os dados originais nunca saem do processo.

### Configuração (variáveis de ambiente)

Adicionadas ao serviço `api` no `docker-compose.yml` (todas têm padrão seguro):
`LLM_API_KEY`, `LLM_BASE_URL` (padrão `https://api.openai.com/v1`),
`LLM_MODEL` (`gpt-4o-mini`), `LLM_TIMEOUT_SEGUNDOS` (5), `LLM_RETRIES` (3),
`LLM_CIRCUIT_FALHAS_PARA_ABRIR` (3), `LLM_CIRCUIT_TIMEOUT_ABERTO` (60) e
`LLM_CUSTO_USD_POR_MILHAO` (2.5) para a estimativa do campo `custo_usd_estimado`
dos logs.

Sem `LLM_API_KEY` o endpoint funciona e responde **503** (verificável sem custo
de tokens); com chave, usa o modelo indicado. `ASSIST_LOG_LEVEL` controla o
nível do logger `assist` (padrão `INFO`).

### Validação manual

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/assist \
  -H 'Content-Type: application/json' \
  -d '{"mode":"summarize","logs":"falhou para joao@empresa.com"}'
# Sem LLM_API_KEY: 503 {"title":"Serviço indisponível", ...}
# Payload inválido: 400 {"title":"Requisição inválida", ...}
```

Logs estruturados do ciclo (apenas texto redigido):

```
assist acao=endpoint_assistir status=falha erro=provedor duracao_ms=405.29 http=401
assist acao=endpoint_assistir status=sucesso duracao_ms=812.40 tentativas=1
       custo_usd_estimado=0.0004 tokens_prompt=128 tokens_output=45
```

Suíte automatizada: 32 testes cobrem `redaction`, `prompts`, `llm_service`
(retry/backoff/circuit breaker) e o endpoint; `pytest.ini` agora cobre também
`--cov=assist`.

### Resultado (DoD da Aula 14)

| Item | Estado |
|---|---|
| `POST /api/v1/assist` com `summarize`/`explain` | ✅ `assist/views.py` |
| `llm_service` com timeout ≤ 5 s, retry + backoff/jitter | ✅ |
| Circuit breaker (aberto → meio-aberto → fechado) | ✅ `circuit_breaker.py` |
| Redação de PII antes do envio e nos logs | ✅ `redaction.py` |
| Erros padronizados 400/502/503 (RFC 7807) | ✅ |
| Telemetria (duração, tentativas, custo, tokens) | ✅ |
| Testes unitários com fakes + fixtures | ✅ 223 testes, 98% cobertura |
| OpenAPI/Spectral, Postman e `CHANGELOG.md` | ✅ |
| Pendências extra-spec registadas | ✅ `specs/issues_da_aula_14.md` |

### Escopo da Aula 14

Modelagem e resiliência do assistente de logs. **Não** foram antecipados:
endpoint de métricas/verbos de Redis para o circuito, cache de respostas por
chave de prompt, guardrails/validação de conteúdo, testes de integração reais,
*streaming* de resposta, rotação segura de `LLM_API_KEY` nem autenticação do
endpoint (o `bearerAuth` continua apenas documentado).
