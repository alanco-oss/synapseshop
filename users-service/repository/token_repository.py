from sqlalchemy.orm import Session
from models.token import Token
from datetime import datetime

class TokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def criar(self, user_id: int, token: str, expira_em: datetime) -> Token:
        novo_token = Token(user_id=user_id, token=token, expira_em=expira_em)
        self.db.add(novo_token)
        self.db.commit()
        self.db.refresh(novo_token)
        return novo_token

    def buscar_por_token(self, token: str) -> Token | None:
        return self.db.query(Token).filter(Token.token == token).first()

    def buscar_por_user_id(self, user_id: int) -> list[Token]:
        return self.db.query(Token).filter(Token.user_id == user_id).all()