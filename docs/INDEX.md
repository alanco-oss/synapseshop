# Índice da Documentação - SynapseShop

## Documentação Principal
| Arquivo | Descrição |
|---|---|
| [README.md](../README.md) | Documentação completa por aula (histórico detalhado, 52KB) |
| [AGENTS.md](../AGENTS.md) | Guia otimizado para agentes de IA (entrypoints, comandos, mapa) |
| [CHANGELOG.md](../CHANGELOG.md) | Histórico de mudanças do projeto |
| [tasks.py](../tasks.py) | Comandos centralizados (test, coverage, lint, check, up, down, clean) |

## Especificações (SpecDD)
| Local | Descrição |
|---|---|
| [specs/](../specs/) | Especificações por aula (`specs_da_aula_*.md`) e diretrizes |
| [specs/README.md](../specs/README.md) | Índice das specs por aula |

## Documentação Técnica
| Arquivo | Descrição |
|---|---|
| [docs/openapi.yaml](openapi.yaml) | Contrato OpenAPI 3.0.3 |
| [docs/checklist_integrador_externo.md](checklist_integrador_externo.md) | Checklist para integradores externos |
| [docs/checklist_ia_safe.md](checklist_ia_safe.md) | Checklist para código gerado por IA |
| [docs/diagrama.svg](diagrama.svg) | Diagrama da arquitetura |

## Postman
| Local | Descrição |
|---|---|
| [postman/](../postman/) | Coleção e ambiente do Postman |
| [postman/README.md](../postman/README.md) | Guia de uso da coleção Postman |

## Histórico e Prompts
| Arquivo | Descrição |
|---|---|
| [docs/historico/PROMPTS.md](../docs/historico/PROMPTS.md) | Histórico completo de prompts IA (27KB) - prefira consultar via índice |
| [docs/historico/](historico/) | Diretório para histórico organizado |

## Mapa por Serviço
| Serviço | Documentação |
|---|---|
| [api/v1/products/](../api/v1/products/) | API Django principal (manage.py) |
| [users-service/](../users-service/) | Serviço FastAPI de usuários (ver `users-service/README.md`) |
| [inventory/](../inventory/) | Serviço FastAPI de inventário |
| [dashboard/](../dashboard/) | Painel Streamlit (porta 8501, live reload) |

## Navegação Rápida por Domínio
| Domínio | Local | Descrição |
|---|---|---|
| Catálogo | `api/v1/products/catalog/` | Categories, Items |
| Pedidos | `api/v1/products/orders/` | Orders, Cache, Mensageria Kafka |
| Assistente IA | `api/v1/products/assist/` | LLM resiliente com redaction |
| Core/Config | `api/v1/products/products/` | Settings, URLs, middleware, exceptions |
