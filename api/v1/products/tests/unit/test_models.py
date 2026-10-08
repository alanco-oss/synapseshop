"""Testes unitários dos modelos do catálogo."""
from catalog.models import Category, Item


def test_category_str_devolve_nome():
    assert str(Category(nome="Livros")) == "Livros"


def test_item_str_devolve_nome():
    assert str(Item(nome="Clean Code", preco="59.99")) == "Clean Code"
