"""Cabeçalhos transversais da API (Aula 13).

O ``X-Trace-Id`` é o identificador de correlação documentado no contrato
OpenAPI. Quando o cliente o envia, ele é preservado; caso contrário é gerado
por requisição. Em ambos os casos o valor é devolvido na resposta e fica
disponível em ``request.trace_id`` para logs.
"""
import uuid


class TraceIdMiddleware:
    header = "X-Trace-Id"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        trace_id = request.headers.get(self.header) or uuid.uuid4().hex
        request.trace_id = trace_id
        response = self.get_response(request)
        response[self.header] = trace_id
        return response
