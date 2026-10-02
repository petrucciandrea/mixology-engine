"""Cache del grafo che non memorizza nulla."""

from __future__ import annotations


class NullGraphSnapshotCache:
    """Implementazione della porta `GraphSnapshotCache` senza Redis.

    Ogni `get` è un miss e ogni `set` non fa nulla, quindi il grafo si
    ricostruisce a ogni richiesta. Non è un ripiego per un guasto — quello
    lo gestisce già `RedisGraphSnapshotCache` — ma la scelta esplicita di
    rinunciare a un'ottimizzazione dove costerebbe più di quanto rende:
    con una dispensa da bar la costruzione del grafo è questione di
    millisecondi, mentre Redis sui piani gratuiti è un servizio in più da
    tenere in vita (ADR-0010).
    """

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, payload: str, ttl_seconds: int) -> None:
        return None
