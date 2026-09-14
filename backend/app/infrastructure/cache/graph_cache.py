"""Cache Redis del grafo delle affinità."""

from __future__ import annotations

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class RedisGraphSnapshotCache:
    """Implementazione della porta `GraphSnapshotCache`.

    Regola di fondo: **una cache che non funziona non deve far fallire una
    richiesta**. Se Redis è irraggiungibile, un `get` si comporta come un
    miss e un `set` non fa nulla; il chiamante ricostruisce il grafo e
    risponde comunque, solo più lentamente. Lasciar propagare l'eccezione
    renderebbe il matcher indisponibile per un guasto in una componente che
    esiste unicamente per farlo andare piu' veloce.

    Il guasto viene registrato — a livello warning, non error: il sistema
    sta degradando, non fallendo — perché una cache che smette di
    funzionare in silenzio si manifesta solo come un rallentamento
    inspiegabile.
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def get(self, key: str) -> str | None:
        try:
            value = await self._client.get(key)
        except RedisError:
            logger.warning("cache del grafo non raggiungibile in lettura", exc_info=True)
            return None
        return str(value) if value is not None else None

    async def set(self, key: str, payload: str, ttl_seconds: int) -> None:
        try:
            await self._client.set(key, payload, ex=ttl_seconds)
        except RedisError:
            logger.warning("cache del grafo non raggiungibile in scrittura", exc_info=True)
