"""Testes de sanidade dos entrypoints WSGI e ASGI."""


def test_wsgi_application_carrega():
    from products.wsgi import application

    assert callable(application)


def test_asgi_application_carrega():
    from products.asgi import application

    assert callable(application)
