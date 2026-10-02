"""La cache nulla: l'adapter usato quando Redis non è configurato."""

from __future__ import annotations

from app.infrastructure.cache import NullGraphSnapshotCache


async def test_a_written_entry_is_never_read_back() -> None:
    """Ogni lettura è un miss: il chiamante ricostruisce il grafo, come
    farebbe con una cache Redis vuota."""
    cache = NullGraphSnapshotCache()

    await cache.set("flavor-graph:v1:abc", '{"nodes": []}', ttl_seconds=300)

    assert await cache.get("flavor-graph:v1:abc") is None
