from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rate_limiter import limiter
from dependencies import get_db, get_usuario_atual, exigir_admin
from repository.user_repository import UserRepository
from repository.token_repository import TokenRepository
from services.auth_service import AuthService, CredenciaisInvalidasError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, dados: LoginRequest, db: Session = Depends(get_db)):
    auth_service = AuthService(UserRepository(db), TokenRepository(db))
    try:
        token = auth_service.login(dados.email, dados.senha)
    except CredenciaisInvalidasError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou senha inválidos")
    return TokenResponse(access_token=token)


@router.get("/me")
def me(usuario: dict = Depends(get_usuario_atual)):
    return usuario


@router.get("/admin-only")
def rota_admin(usuario: dict = Depends(exigir_admin)):
    return {"mensagem": "Você é admin", "usuario": usuario}