import os
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


def _get_database_url() -> URL:
    """Cria URL de conexao segura usando variaveis de ambiente."""
    db_user = os.getenv("DB_USER") or os.getenv("POSTGRES_USER", "synapse")
    db_password = os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD", "synapseshop")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME") or os.getenv("POSTGRES_DB", "synapseshop")

    return URL.create(
        "postgresql+psycopg2",
        username=db_user,
        password=db_password,
        host=db_host,
        port=int(db_port),
        database=db_name,
    )


def _build_engine():
    """Cria engine SQLAlchemy com pooling, timeouts e SSL/TLS."""
    url = _get_database_url()
    sslmode = os.getenv("DB_SSLMODE", "require")
    connect_args = {
        "sslmode": sslmode,
        "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
    }
    return create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
    )


ENGINE = _build_engine()


@contextmanager
def get_connection():
    """Retorna conexao com transacao segura (autocommit=False por padrao)."""
    conn = ENGINE.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_cursor():
    """Atalho para obter cursor SQLAlchemy."""
    with get_connection() as conn:
        yield conn


def fetch_all(query: str, params: dict | None = None):
    """Executa consulta parametrizada e retorna lista de dicts."""
    params = params or {}
    with get_connection() as conn:
        result = conn.execute(text(query), params)
        if result.returns_rows:
            keys = result.keys()
            return [dict(zip(keys, row, strict=False)) for row in result.fetchall()]
        return []


def fetch_one(query: str, params: dict | None = None):
    """Executa consulta parametrizada e retorna um unico registro ou None."""
    params = params or {}
    with get_connection() as conn:
        result = conn.execute(text(query), params)
        if not result.returns_rows:
            return None
        row = result.fetchone()
        if row is None:
            return None
        keys = result.keys()
        return dict(zip(keys, row, strict=False))
