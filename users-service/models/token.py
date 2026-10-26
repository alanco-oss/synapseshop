
from database import Base
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String


class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(500), unique=True, nullable=False)
    expira_em = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_tokens_user_id_expira_em", "user_id", "expira_em"),
    )
