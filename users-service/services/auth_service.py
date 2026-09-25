from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from database import JWT_ALGORITHM, JWT_SECRET
from repository.token_repository import TokenRepository
from repository.user_repository import UserRepository

TOKEN_EXPIRACAO = timedelta(hours=1)


class CredenciaisInvalidasError(Exception):
    pass


class TokenExpiradoError(Exception):
    pass


class TokenInvalidoError(Exception):
    pass


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository,
        token_repository: TokenRepository,
    ):
        self.user_repository = user_repository
        self.token_repository = token_repository

    def login(self, email: str, senha: str) -> str:
        usuario = self.user_repository.buscar_por_email(email)
        if usuario is None or not bcrypt.checkpw(
            senha.encode("utf-8"),
            usuario.senha_hash.encode("utf-8"),
        ):
            raise CredenciaisInvalidasError("Email ou senha inválidos")

        expira_em = datetime.now(UTC) + TOKEN_EXPIRACAO
        token = jwt.encode(
            {
                "user_id": usuario.id,
                "role": usuario.role.value,
                "exp": expira_em,
            },
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )
        self.token_repository.criar(
            user_id=usuario.id,
            token=token,
            expira_em=expira_em,
        )
        return token

    def validar_token(self, token: str) -> dict:
        try:
            return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise TokenExpiradoError("Token expirado") from None
        except jwt.InvalidTokenError:
            raise TokenInvalidoError("Token inválido") from None