from sqlalchemy.orm import Session
from models.user import User
from models.user import UserRole

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def criar(self, email: str, nome: str, senha_hash: str) -> User:
        usuario = User(email=email, nome=nome, senha_hash=senha_hash)
        self.db.add(usuario)
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def buscar_por_id(self, id_: int) -> User | None:
        return self.db.query(User).filter(User.id == id_).first()

    def buscar_por_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def listar(self, role: UserRole | None = None, offset: int = 0, limite: int = 10) -> list[User]:
        query = self.db.query(User)
        if role is not None:
            query = query.filter(User.role == role)
        return query.offset(offset).limit(limite).all()
    def contar(self, role: UserRole | None = None) -> int:
        query = self.db.query(User)
        if role is not None:
            query = query.filter(User.role == role)
        return query.count()


