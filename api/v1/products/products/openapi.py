"""Disponibilização interativa do contrato OpenAPI (Aula 13).

O ficheiro ``docs/openapi.yaml`` é a fonte de verdade do contrato. Aqui é
apenas servido em ``/api/v1/schema/`` e consumido pelas interfaces Swagger UI
(``/api/v1/docs/``) e ReDoc (``/api/v1/redoc/``), carregadas por CDN.
"""
from pathlib import Path

from django.http import HttpResponse

SCHEMA_URL = "/api/v1/schema/"


def _localizar_schema():
    for pasta in Path(__file__).resolve().parent.parents:
        candidato = pasta / "docs" / "openapi.yaml"
        if candidato.is_file():
            return candidato
    return None


def schema(request):
    caminho = _localizar_schema()
    if caminho is None:
        return HttpResponse(
            "openapi.yaml não encontrado", status=404, content_type="text/plain"
        )
    return HttpResponse(
        caminho.read_text(encoding="utf-8"), content_type="application/yaml"
    )


_SWAGGER = """<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SynapseShop API — Swagger UI</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js" crossorigin></script>
  <script>
    window.addEventListener("load", function () {
      window.ui = SwaggerUIBundle({
        url: "%(schema)s",
        dom_id: "#swagger-ui",
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis],
        layout: "BaseLayout",
      });
    });
  </script>
</body>
</html>
""" % {"schema": SCHEMA_URL}

_REDOC = """<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SynapseShop API — ReDoc</title>
  <style>body { margin: 0; padding: 0; }</style>
</head>
<body>
  <redoc spec-url="%(schema)s"></redoc>
  <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body>
</html>
""" % {"schema": SCHEMA_URL}


def docs(request):
    return HttpResponse(_SWAGGER, content_type="text/html")


def redoc(request):
    return HttpResponse(_REDOC, content_type="text/html")
