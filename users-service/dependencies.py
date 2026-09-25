# dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import SessionLocal
from repository.user_repository import UserRepository
from repository.token_repository import TokenRepository
from services.auth_service import AuthService, TokenExpiradoError, TokenInvalidoError

security = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_usuario_atual(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(UserRepository(db), TokenRepository(db))
    try:
        payload = auth_service.validar_token(credentials.credentials)
    except (TokenExpiradoError, TokenInvalidoError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return payload


def exigir_admin(usuario: dict = Depends(get_usuario_atual)):
    if usuario["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    return usuario


