import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://synapse:synapseshop@localhost:5432/synapseshop"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
JWT_SECRET = os.getenv("JWT_SECRET", "chave-de-desenvolvimento-trocar-em-producao")
JWT_ALGORITHM = "HS256"