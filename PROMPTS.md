# PROMPTS.md

Histórico de uso de IA generativa no desenvolvimento do SynapseShop.

## Registro

### Aula 3 — Docker Essencial: Do Básico ao Compose

#### 1. Dockerfile multistage

- **Ferramenta:** OpenCode
- **Prompt:** "Reveja o plano de conteinerização da Aula 2 e gere um Dockerfile
  para a Aula 3 com multistage build, cache eficiente de dependências e
  execução como usuário não-root, sem antecipar Django REST Framework, FastAPI
  ou PostgreSQL com modelos de dados."
- **Correções aplicadas:** `HEALTHCHECK` usa uma forma inline —
  `python -c "import urllib.request; urllib.request.urlopen(...)"` — pois a
  imagem `python:3.12-slim` não inclui `curl`/`wget`; a forma inline foi
  escolhida (em vez de `python -m`) porque permite tratar exceções e retornar o
  exit code correto que o HEALTHCHECK do Docker precisa para determinar status
  "healthy"/"unhealthy"; dependências instaladas
  com `pip install --user` na stage builder e copiadas para a stage runtime;
  com `requirements.txt` vazio o `pip install --user` não cria `/root/.local`,
  o que quebrava o `COPY --from=builder` — corrigido com `mkdir -p /root/.local`
  após a instalação.
- **Impacto:** imagem menor, executada como usuário não-root e com cache de
  dependências (o `requirements.txt` é copiado antes do código-fonte).

#### 2. Docker Compose (API + Banco de Dados)

- **Ferramenta:** OpenCode
- **Prompt:** "Crie um docker-compose.yml orquestrando a API e o banco de
  dados para a Aula 3, com injeção de variáveis de ambiente mínimas,
  healthcheck do banco e um único comando para subir o ambiente."
- **Correções aplicadas:** PostgreSQL mantido apenas como serviço de
  orquestração (sem models/migrações) para respeitar a regra de não antecipação
  da Aula 6; `api` aguarda o `db` ficar saudável via `depends_on.condition`.
- **Impacto:** `docker compose up` inicia API + banco e a API expõe `/health`.

#### 3. Rota /health

- **Ferramenta:** OpenCode
- **Prompt:** "Implemente a rota /health para monitoramento de disponibilidade
  sem utilizar frameworks (FastAPI/DRF), apenas a biblioteca padrão do Python."
- **Impacto:** `GET /health` responde `200 {"status": "ok", ...}` expondo o
  estado da API e o `DB_HOST` configurado.

---

*Este arquivo crescerá a cada aula conforme o uso de IA generativa no projeto.*