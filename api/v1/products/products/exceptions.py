"""Tratamento padronizado de erros (Aula 13).

Converte as respostas de erro do DRF para o envelope inspirado na RFC 7807
(``type``/``title``/``status``/``detail``/``instance``) descrito no contrato
OpenAPI. Para não quebrar clientes anteriores à Aula 13, os erros de validação
mantêm também as chaves por campo no nível de topo (formato nativo do DRF) e
são replicados em ``errors``.
"""
from rest_framework.views import exception_handler as drf_exception_handler

TITULOS = {
    400: "Requisição inválida",
    401: "Não autenticado",
    402: "Pagamento requerido",
    403: "Acesso negado",
    404: "Recurso não encontrado",
    405: "Método não permitido",
    409: "Conflito de estado",
    415: "Tipo de mídia não suportado",
    429: "Demasiadas requisições",
    500: "Erro interno do servidor",
    502: "Gateway inválido",
    503: "Serviço indisponível",
}


def tratamento_de_erro(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    status_code = response.status_code
    dados = response.data
    request = context.get("request")

    corpo = {
        "type": "about:blank",
        "title": TITULOS.get(status_code, "Erro"),
        "status": status_code,
        "detail": TITULOS.get(status_code, "Erro"),
        "instance": getattr(request, "path", ""),
    }

    if isinstance(dados, dict) and set(dados.keys()) == {"detail"}:
        corpo["detail"] = str(dados["detail"])
    else:
        corpo["errors"] = dados
        if isinstance(dados, dict):
            for campo, mensagem in dados.items():
                corpo.setdefault(campo, mensagem)

    response.data = corpo
    return response
