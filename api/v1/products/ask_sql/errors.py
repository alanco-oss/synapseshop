"""Erros de dominio do Texto-para-SQL (Aula 21).

Sao independentes do DRF para que a extracao, a validacao e a execucao possam
ser testadas isoladamente. A view traduz estes erros para o envelope HTTP
padrao (RFC 7807).
"""


class ErroConsultaSQL(Exception):
    """Base para falhas ao interpretar, validar ou executar a SQL gerada."""


class RespostaInvalida(ErroConsultaSQL):
    """A resposta da LLM nao contem um JSON/SQL utilizavel."""


class SQLInvalido(ErroConsultaSQL):
    """A SQL extraida nao pode ser executada como consulta de leitura."""


class SQLInseguro(ErroConsultaSQL):
    """A SQL viola a allow-list de comandos/tabelas."""


class ErroExecucaoSQL(ErroConsultaSQL):
    """O banco de dados rejeitou a consulta (sintaxe, timeout, permissao)."""
