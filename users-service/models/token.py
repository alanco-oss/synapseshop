import os
import sys

from sqlalchemy import Index, ForeignKey, DateTime, Column, Integer, String, Index
from database import Base 

class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(500), unique=True, nullable=False)
    expira_em = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_tokens_user_id_expira_em", "user_id", "expira_em"),
    )