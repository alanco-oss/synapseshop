# SynapseShop — Infraestrutura Docker (Aula 3)

## Objetivo

Evolução da conteinerização da Aula 2: imagem otimizada com *multistage build*,
execução como usuário não-root, orquestração da API com o banco de dados via
Docker Compose e rota `/health` para monitoramento básico.

## Estrutura

```
Aula 3/
├── api/                 # Entrypoints e roteamento (Aula 4+)
├── services/            # Lógica de negócio (Aula 4+)
├── repositories/        # Acesso a dados (Aula 6+)
├── specs/               # Especificações do curso
├── .dockerignore
├── app.py               # Servidor HTTP stdlib com rota /health
├── docker-compose.yml   # Orquestração API + PostgreSQL
├── Dockerfile           # Multistage, usuário não-root, cache de deps
└── requirements.txt     # Dependências (vazio na Aula 3)
```

## Como subir o ambiente

Com **um único comando** (preferir a variante sem hífen em versões novas do
Compose; o curso também aceita `docker-compose up`):

```bash
docker compose up --build
```

Para rodar em segundo plano:

```bash
docker compose up -d --build
```

## Validação da rota /health

```bash
curl http://127.0.0.1:8000/health
# {"status": "ok", "app": "synapseshop-api", "db_host": "db"}
```

*Nota:* em máquinas Windows, `curl http://localhost:8000/health` pode atingir um
listener IPv6 do próprio sistema (`dllhost`) em vez do contêiner — prefira
`127.0.0.1`.

O container também possui `HEALTHCHECK` interno (imagem está *healthy* apenas
quando `/health` responde 200).

## Como derrubar os contêineres

```bash
docker compose down        # remove contêineres e a rede
docker compose down -v     # remove também o volume do banco (pgdata)
```

## Monitoramento de logs

```bash
docker compose logs                      # logs de todos os serviços
docker compose logs -f api               # segue os logs da API em tempo real
docker compose logs -f db                # logs do PostgreSQL
docker compose ps                        # estado dos serviços
```

## Análise das camadas da imagem

```bash
docker history synapseshop-api:latest    # ou docker history aula3-api
```

Use `--no-trunc` para ver o comando completo de cada camada.

## Variáveis de ambiente

As variáveis essenciais são injetadas pelo Compose com valores padrão
(sobrescrevíveis via arquivo `.env` ou variáveis do shell):

| Serviço | Variável | Padrão |
|---|---|---|
| `api` | `APP_NAME` | `synapseshop-api` |
| `api` | `APP_HOST` | `0.0.0.0` |
| `api` | `APP_PORT` | `8000` |
| `api` | `DB_HOST` | `db` |
| `db` | `POSTGRES_USER` | `synapse` |
| `db` | `POSTGRES_PASSWORD` | `synapseshop` |
| `db` | `POSTGRES_DB` | `synapseshop` |

## Escopo da Aula 3

Apenas infraestrutura de conteinerização. **Não** foram antecipados: Django
REST Framework, FastAPI, modelos de banco de dados, migrações, mensageria ou
lógicas de IA (Aulas futuras). O PostgreSQL roda apenas como serviço de
orquestração, sem código de acesso a dados.