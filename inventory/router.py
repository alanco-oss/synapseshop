from fastapi import APIRouter, Depends, Header

from models import Categoria


def validar_categoria(
    x_internal_service: Categoria = Header(alias="X-Internal-Service"),
):
    return x_internal_service


router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(validar_categoria)],
)


@router.get("/")
def list_inventory():
    return []