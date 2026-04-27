"""
db_layer.py — Camada de acesso ao banco de dados com pooling de conexões.

Substitui o context manager `get_db()` do app.py monolítico por um pool
reutilizável (ThreadedConnectionPool), reduzindo a latência de handshake
TLS/TCP com o Supabase em ~50–200ms por request.

Pattern: Object Pool
Complexidade: O(1) amortizado por acquire/release.

Uso:
    from db_layer import acquire_conn

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool
from dotenv import load_dotenv

load_dotenv()

# ── Configuração do pool ──────────────────────────────────────────────────────

_DATABASE_URL: str = os.environ["SUPABASE_DATABASE_URL"]

# minconn=2: conexões sempre abertas; maxconn=10: limite de concorrência.
# Ajuste conforme o plano do Supabase (Free = 60 conexões simultâneas).
_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None


def init_pool(minconn: int = 2, maxconn: int = 10) -> None:
    """
    Inicializa o pool de conexões PostgreSQL.

    Deve ser chamado uma vez durante o startup da aplicação Flask,
    dentro de `app.app_context()` ou antes de `app.run()`.

    Args:
        minconn: Número mínimo de conexões mantidas abertas.
        maxconn: Número máximo de conexões simultâneas permitidas.

    Raises:
        psycopg2.OperationalError: Se não for possível conectar ao banco.
        RuntimeError: Se chamado mais de uma vez.
    """
    global _pool
    if _pool is not None:
        return  # Idempotente — não recria se já existe
    _pool = psycopg2.pool.ThreadedConnectionPool(
        minconn,
        maxconn,
        _DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def close_pool() -> None:
    """
    Fecha todas as conexões do pool.

    Deve ser chamado no teardown da aplicação (atexit ou signal handler).
    Seguro chamar mesmo se o pool não foi inicializado.
    """
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager
def acquire_conn() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Context manager que fornece uma conexão do pool com commit/rollback automático.

    Comportamento:
        - Realiza commit se o bloco terminar sem exceção.
        - Realiza rollback caso ocorra qualquer exceção.
        - Devolve a conexão ao pool no bloco `finally` (mesmo em erro).

    Yields:
        Conexão psycopg2 com cursor_factory RealDictCursor configurado.

    Raises:
        RuntimeError: Se `init_pool()` não foi chamado antes.
        psycopg2.pool.PoolError: Se não houver conexões disponíveis no pool.

    Example:
        with acquire_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM celulares")
                rows = cur.fetchall()
    """
    if _pool is None:
        raise RuntimeError(
            "Pool não inicializado. Chame init_pool() antes de usar acquire_conn()."
        )

    conn: Optional[psycopg2.extensions.connection] = None
    try:
        conn = _pool.getconn()
        yield conn
        conn.commit()
    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            _pool.putconn(conn)


# ── Helpers de resultado ──────────────────────────────────────────────────────

def row_to_dict(
    row: Optional[psycopg2.extras.RealDictRow],
) -> Optional[dict]:
    """
    Converte uma linha RealDictRow em dicionário Python puro.

    Args:
        row: Linha retornada pelo cursor psycopg2, ou None.

    Returns:
        Dicionário com os dados da linha, ou None.
    """
    return dict(row) if row else None


def rows_to_list(rows: list[psycopg2.extras.RealDictRow]) -> list[dict]:
    """
    Converte lista de RealDictRow em lista de dicionários Python puros.

    Args:
        rows: Lista de linhas retornadas pelo cursor psycopg2.

    Returns:
        Lista de dicionários.
    """
    return [dict(r) for r in rows]


def fetch_all(
    cur: psycopg2.extensions.cursor,
    query: str,
    params: tuple = (),
) -> list[dict]:
    """Executa query e retorna todos os resultados como lista de dicts."""
    cur.execute(query, params)
    return rows_to_list(cur.fetchall())


def fetch_one(
    cur: psycopg2.extensions.cursor,
    query: str,
    params: tuple = (),
) -> Optional[dict]:
    """Executa query e retorna o primeiro resultado como dict ou None."""
    cur.execute(query, params)
    return row_to_dict(cur.fetchone())
