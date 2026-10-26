# SynapseShop — Documentação do projeto

## Comandos de operação

Todos os comandos recorrentes do projeto estão centralizados em `tasks.py`
(Python puro — funciona igual em Windows, Linux e macOS, sem instalar nada).

```bash
python tasks.py --help        # lista completa
python tasks.py test          # suite de testes (223 testes, ~2s, sem Docker)
python tasks.py coverage      # suite + relatório HTML de cobertura
python tasks.py lint          # ruff + lint do contrato OpenAPI (Spectral)
python tasks.py check         # lint + testes: verificação antes do commit
python tasks.py up            # sobe o stack completo via docker compose
python tasks.py down          # derruba o stack e remove os volumes
python tasks.py clean         # remove caches e artefactos
```

A suíte de testes **não precisa de Docker, Postgres, Redis nem Kafka**: corre
em SQLite em memória com *fakes* para as dependências externas. Para validar
contra o PostgreSQL de produção, `DB_ENGINE=postgres pytest`.

A CI (`.github/workflows/ci.yml`) corre a suíte nos dois motores de base de
dados, aplica o linter e o lint do OpenAPI, e constrói as imagens Docker.

---


## Documentacao por Aula

- [Aula 03](docs/aulas/AULA_03.md)
- [Aula 08](docs/aulas/AULA_08.md)
- [Aula 09](docs/aulas/AULA_09.md)
- [Aula 10](docs/aulas/AULA_10.md)
- [Aula 11](docs/aulas/AULA_11.md)
- [Aula 12](docs/aulas/AULA_12.md)
- [Aula 13](docs/aulas/AULA_13.md)
- [Aula 14](docs/aulas/AULA_14.md)

## Documentacao Adicional

- [AGENTS.md](AGENTS.md)
- [docs/INDEX.md](docs/INDEX.md)
- [CHANGELOG.md](CHANGELOG.md)
- [docs/openapi.yaml](docs/openapi.yaml)
- [postman/](postman/)
- [specs/](specs/)


## Aula 19 - Conexao Segura, SQL Injection e Painel Streamlit

### Executar
```bash
python tasks.py up
# ou
docker compose up --build
```

Painel disponivel em: **http://localhost:8501** (health: `http://localhost:8501/_stcore/health`).
O servico `dashboard` usa bind-mount em `./dashboard:/app`, por isso alteracoes no
codigo refletem em tempo real (live reload).

### Variaveis de ambiente (Dashboard)
| Variavel | Padrao | Descricao |
|---|---|---|
| DB_HOST | db (compose) / localhost | Host do PostgreSQL |
| DB_PORT | 5432 | Porta |
| DB_NAME / POSTGRES_DB | synapseshop | Banco de dados |
| DB_USER / POSTGRES_USER | synapse | Usuario |
| DB_PASSWORD / POSTGRES_PASSWORD | synapseshop | Senha |
| DB_SSLMODE | require (codigo) / prefer (compose local) | Modo SSL/TLS |

> O PostgreSQL do `docker-compose.yml` nao tem TLS configurado. No ambiente local o
> compose injeta `DB_SSLMODE=prefer` (tenta TLS e recorre a ligacao normal). Em
> producao defina `DB_SSLMODE=require`.

### Seguranca
- Zero Interpolacao: Todas as consultas SQL utilizam text() com bind parameters.
- SQL Injection: Filtros dinamicos devem usar allow-list. Listas utilizam = ANY(:lista).
- Conexao: SQLAlchemy com pool_pre_ping, timeouts e connect_args com sslmode configuravel.
