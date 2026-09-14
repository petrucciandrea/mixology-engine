"""Client Redis asincrono, con pool creato pigramente.

Stessa ragione di `db/session.py`: creare il pool all'import del modulo
obbligherebbe chiunque importi questo file ad avere un `REDIS_URL`
valido, anche quando Redis non c'entra nulla con ciò che sta facendo.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_pool() -> ConnectionPool:
    return ConnectionPool.from_url(get_settings().redis_url, decode_responses=True)


async def redis_scope() -> AsyncGenerator[Redis, None]:
    """Un client per richiesta, sul pool condiviso.

    Il client viene chiuso al termine, ma il pool sopravvive: chiudere il
    client restituisce la connessione al pool, non la distrugge.
    """
    client = Redis(connection_pool=get_pool())
    try:
        yield client
    finally:
        await client.aclose()


async def dispose_pool() -> None:
    """Chiude il pool. Invocato allo spegnimento dell'applicazione."""
    if get_pool.cache_info().currsize:
        await get_pool().aclose()
        get_pool.cache_clear()
