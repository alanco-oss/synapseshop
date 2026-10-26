from dependencies import exigir_admin, get_db
from fastapi import APIRouter, Depends
from models.user import UserRole
from repository.user_repository import UserRepository
from schemas import UserPaginados
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/", response_model=UserPaginados)
def listar_usuarios(
    role: UserRole | None = None,
    page: int = 1,
    size: int = 10,
    usuario: dict = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    repo = UserRepository(db)
    offset = (page - 1) * size

    usuarios = repo.listar(role=role, offset=offset, limite=size)
    total = repo.contar(role=role)

    return UserPaginados(
        total=total,
        page=page,
        size=size,
        usuarios=usuarios,)
