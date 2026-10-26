# Manual de Prompts
## 1. Contexto
- O prompt tem que ter o cotexto de em que aula estamos e o que está sendo esperado de intenção com o próximo comando.
## 2. Comando
- Ser claro com as intenções, sendo esperado que se tenha noção do que o que está sendo pedido previamente.
- Delimitar as restrições da aula.
- Não copiar e colar dos specs das aulas.
## 3. Requisitos técnicos
- Dizer os modelos de dados esperados (campos, tipos).
- Quais dependências são permitidas/esperadas.
- Formato de resposta padrão esperado (sucesso e erro).
## 4. Critérios de validação
- Um resultado esperado explicíta o que está sendo feito e se o que está sendo feito está dentro do pedido.
- Validação se o que está prestes a ser feito se comunica com o resto do projeto.
- Se a IA fez algo fora do pedido indica que o prompt não foi claro o suficiente. 

## Aula 19 - Conexão Segura, SQL Injection e Painel Streamlit
- Contexto: Implementacao de conexao segura com SSL/TLS, pooling, consultas parametrizadas (mitigacao SQLi), painel Streamlit com filtros/cache e orquestracao via Docker Compose com live reload.
- Decisoes: Criado modulo dashboard/ isolado com db.py (SQLAlchemy + timeouts + sslmode=require), app.py com @st.cache_data(ttl=60), Dockerfile proprio e bind-mount.
- Validacao: Consultas parametrizadas com text() + params, filtros dinâmicos por data/status; painel em http://localhost:8501
