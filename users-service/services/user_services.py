import bcrypt
from repository.user_repository import UserRepository
from models.user import User


class EmailJaExisteError(Exception):
    pass


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def criar_usuario(self, email: str, nome: str, senha: str) -> User:
        if self.repository.buscar_por_email(email) is not None:
            raise EmailJaExisteError(f"Email {email} já cadastrado")

        senha_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt())
        return self.repository.criar(
            email=email,
            nome=nome,
            senha_hash=senha_hash.decode("utf-8"),
        )

    def buscar_usuario(self, id_: int) -> User | None:
        return self.repository.buscar_por_id(id_)