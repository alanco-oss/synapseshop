# Postman - SynapseShop API

## Arquivos
| Arquivo | Descrição |
|---|---|
| [collections/SynapseShop API.postman_collection.json](collections/SynapseShop%20API.postman_collection.json) | Coleção principal com todos os endpoints (grande - evite ler inteiro) |
| [environments/SynapseShop Local.postman_environment.json](environments/SynapseShop%20Local.postman_environment.json) | Ambiente local |
| [globals/workspace.globals.yaml](globals/workspace.globals.yaml) | Variáveis globais |

## Como Usar
- **Importar**: Coleção + Environment no Postman/Insomnia
- **Variáveis**: `baseUrl`, `token`, `traceId`, `idempotencyKey`, `cat_id`, `item_id`, `pedido_id`
- **Base URL padrão**: `http://127.0.0.1:8000` (conforme docker-compose)

## Dica para Agentes
**Não leia a coleção JSON inteira.** Use `grep` para buscar por endpoint específico (ex: `"/api/v1/pedidos"` ou `"assist"`) ou procure por pasta/endpoint no arquivo. A coleção é grande e polui o contexto.
