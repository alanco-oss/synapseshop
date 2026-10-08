# Issues a criar — pendências da Aula 12

Pendências identificadas durante a Aula 12, prontas a colar no GitHub
(`gh issue create` ou interface web). Uma secção por issue.

---

## 1. Testes automatizados para `users-service` e `inventory-service`

**Título:** `tests: cobrir users-service e inventory-service com pytest`

**Corpo:**

A suíte criada na Aula 12 cobre apenas a API Django principal
(`api/v1/products`). Os restantes serviços do repositório continuam sem
testes automatizados.

**A fazer:**

- [ ] Configurar `pytest` + `pytest-django`/`httpx` em cada serviço
      (`users-service`, `inventory-service`).
- [ ] `conftest.py` com fixtures de BD efémera e cliente HTTP.
- [ ] Testes unitários dos serviços/utilitários críticos.
- [ ] Pelo menos um teste de integração por serviço (ciclo de vida de um
      recurso, com verificação de *status codes* e efeitos na BD).
- [ ] Meta de cobertura ≥ 85% por serviço.

---

## 2. Pipeline de CI (GitHub Actions) a correr `pytest`

**Título:** `ci: correr a suíte pytest num workflow do GitHub Actions`

**Corpo:**

Hoje os testes são executados manualmente
(`docker compose exec api pytest`). Não há verificação automática em `push`/PR.

**A fazer:**

- [ ] Workflow que faz `docker compose build api` e corre
      `docker compose exec -T api pytest`.
- [ ] Serviços `db`/`redis`/`redpanda` saudáveis antes dos testes
      (healthchecks do compose).
- [ ] Publicar o relatório de cobertura como artefacto / resumo do PR.
- [ ] Correr em `push` para `main` e em `pull_request`.

---

## 3. Gate de cobertura `--cov-fail-under`

**Título:** `ci: ativar gate de cobertura (--cov-fail-under=85)`

**Corpo:**

A cobertura é apenas *reportada* (`--cov-report=term-missing`), sem valor
mínimo obrigatório. Como efeito, uma regressão de cobertura passa
despercebida.

**A fazer:**

- [ ] Definir a meta acordada (proposta: 85% global).
- [ ] Adicionar `--cov-fail-under=85` ao `addopts`/comando do CI.
- [ ] Documentar a meta no `README.md`.

**Depende de:** issue #2 (pipeline de CI).

---

## 4. Duplicação do registo de `auth_router` em `users-service/main.py`

**Título:** `fix: registo duplicado de auth_router em users-service`

**Corpo:**

`include_router` do `auth_router` aparece mais do que uma vez, o que pode
duplicar rotas no OpenAPI/roteamento.

**A fazer:**

- [ ] Confirmar a duplicação e remover o registo redundante.
- [ ] Corrigir a causa (import/cópia repetida).

---

## 5. Remover `users-service/teste.py`

**Título:** `chore: remover users-service/teste.py (ficheiro residual)`

**Corpo:**

Ficheiro de rascunho que ficou no repositório sem função.

**A fazer:**

- [ ] Confirmar que não é importado por nenhum módulo.
- [ ] Remover o ficheiro.
