"""Client Redis asincrono, istanziato una sola volta (pool di connessioni)."""

from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings

_settings = get_settings()

_pool: ConnectionPool = ConnectionPool.from_url(_settings.redis_url, decode_responses=True)


def get_redis() -> Redis:
    """Dependency FastAPI: restituisce un client legato al pool condiviso."""
    return Redis(connection_pool=_pool)
