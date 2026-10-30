from rest_framework.exceptions import APIException


class ConsultaIndisponivel(APIException):
    status_code = 503
    default_detail = "A consulta em linguagem natural esta indisponivel no momento."
    default_code = "servico_indisponivel"


class ProvedorIndisponivel(APIException):
    status_code = 502
    default_detail = "O provedor de LLM devolveu um erro."
    default_code = "provedor_invalido"


class SQLEntidadeInvalida(APIException):
    status_code = 422
    default_detail = "Nao foi possivel executar a consulta SQL gerada."
    default_code = "sql_invalido"
