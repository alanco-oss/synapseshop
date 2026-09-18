from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class Categoria(str, Enum):
    catalog = "catalog"
    orders = "orders"
    payment = "payment"
    notification = "notification"


class TipoMovimento(str, Enum):
    entrada = "entrada"
    saida = "saida"


class Produto(BaseModel):
    nome: str = Field(min_length=1)
    preco: Decimal = Field(gt=0)
    estoque: int = Field(default=0, ge=0)
    categoria: Categoria


class Estoque(BaseModel):
    produto: str = Field(min_length=1)
    quantidade: int = Field(ge=0)
    categoria: Categoria


class MovimentoEstoque(BaseModel):
    produto: str = Field(min_length=1)
    tipo: TipoMovimento
    quantidade: int = Field(gt=0)
    categoria: Categoria