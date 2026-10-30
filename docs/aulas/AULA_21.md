## Aula 21 — Consulta de Dados em Linguagem Natural (Texto-para-SQL)

Novo app `ask_sql` (`api/v1/products/ask_sql/`) expõe `POST /api/v1/ask_sql`:
recebe uma pergunta de negócio em português, injeta o schema das tabelas
permitidas no prompt da LLM, extrai a query gerada, valida que é somente
leitura e executa-a com limite de linhas. O painel Streamlit ganha a aba
**"Consulta em Linguagem Natural"**.

### Objetivo

- Endpoint `POST /api/v1/ask_sql` (aceita também `/api/v1/ask_sql/`).
- Reutilizar a resiliência da Aula 14 (`timeout`, retries, backoff, circuit
  breaker, redação de PII e telemetria) sem alterar o contrato de `/assist`.
- Expor apenas as tabelas geridas pelo Django: `orders_order`,
  `catalog_item` e `catalog_category`.
- Devolver o SQL gerado, as colunas e os resultados em JSON.
- Exibir no Streamlit o SQL e a tabela de resultados.

### Contrato

Pedido:

```json
{
  "question": "Quais os 5 últimos pedidos?",
  "temperature": 0.0,
  "max_tokens": 512
}
```

- `question`: string obrigatória (máximo configurável, padrão 1000);
- `temperature`: 0.0–1.0 (padrão `0.0`);
- `max_tokens`: 1–4096 (padrão `512`).

Resposta `200`:

```json
{
  "question": "Quais os 5 últimos pedidos?",
  "sql": "SELECT id, status, total, created_at FROM orders_order ORDER BY created_at DESC LIMIT 5",
  "columns": ["id", "status", "total", "created_at"],
  "results": [
    {"id": 12, "status": "paid", "total": 129.9, "created_at": "2026-01-15T12:00:00Z"}
  ],
  "row_count": 1,
  "truncated": false,
  "meta": {
    "tokens_prompt": 320,
    "tokens_output": 42,
    "llm_ms": 840.5,
    "execution_ms": 3.2
  }
}
```

Erros:

| Código | Cenário |
|---|---|
| 400 | payload inválido ou campo desconhecido |
| 422 | SQL insegura, inválida ou falha de execução |
| 502 | provedor de LLM devolveu 4xx determinístico |
| 503 | retries esgotados ou circuito aberto |

### Fluxo

1. `AskSqlSerializer` valida o payload e rejeita campos desconhecidos.
2. A pergunta é redigida com `assist.redaction.redigir()`.
3. `ask_sql.schema.construir_schema_ddl()` gera o DDL a partir de
   `Model._meta` (sem consultar `information_schema`).
4. `ask_sql.prompts.montar_mensagens_sql()` constrói o prompt com regras de
   segurança e exemplos.
5. `assist.llm_service.chamar_llm_com_mensagens()` chama o provedor com
   retry/circuit breaker e telemetria `acao=ask_sql`.
6. `ask_sql.extraction.extrair_sql()` aceita JSON puro, JSON em markdown,
   bloco ```` ```sql ```` ou SQL puro.
7. `ask_sql.safety.validar_sql()` aplica a allow-list, bloqueia DML/DDL,
   valida tabelas/colunas e injeta `LIMIT` quando ausente.
8. `ask_sql.execution.executar_sql()` executa em transação read-only,
   converte tipos para JSON e limita as linhas.

### Segurança

- Apenas `SELECT`/`WITH ... SELECT`, uma única instrução.
- Palavras proibidas: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`,
  `TRUNCATE`, `CREATE`, `GRANT`, `COPY`, `CALL`, `INTO`, `SET`, etc.
- Comentários e múltiplas instruções são rejeitados.
- Tabelas fora da allow-list e colunas sensíveis são rejeitadas.
- PostgreSQL: `SET TRANSACTION READ ONLY` + `SET LOCAL statement_timeout`.
- SQLite (testes): `PRAGMA query_only = ON` (revertido no final).
- `LIMIT` injetado quando ausente e `fetchmany(max_rows + 1)` para marcar
  `truncated`.

> Nota: a API continua anónima, como o resto do projeto. A allow-list limita
> mutações, mas não impede leitura de catálogo/pedidos. Uma camada de
> autenticação/throttle pode ser adicionada numa aula futura.

### Interface Streamlit

A aba **"Consulta em Linguagem Natural"** em `dashboard/app.py`:

- campo de pergunta e exemplos prontos;
- `POST {API_BASE_URL}/api/v1/ask_sql` com timeout de 30 s;
- exibe `st.code(sql, language="sql")` e `st.dataframe(results)`;
- mostra `row_count`, tempo de execução, tokens e aviso de truncamento.

### Testes

Novos ficheiros em `api/v1/products/tests/unit/`:

- `test_ask_sql_endpoint.py` — 200/400/422/502/503, defaults, redação e
  schema no payload.
- `test_ask_sql_prompts.py` — schema exposto e regras do prompt.
- `test_sql_extraction.py` — formatos de resposta da LLM.
- `test_sql_safety.py` — allow-list, DML/DDL, comentários e `LIMIT`.
- `test_sql_execution.py` — execução, conversão JSON e truncamento.

Executar com `python tasks.py test` (SQLite in-memory) e, quando houver
PostgreSQL, `DB_ENGINE=postgres pytest`.
