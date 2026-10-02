"""Adapter di cache (Redis, o nessuna cache)."""

from __future__ import annotations

from .graph_cache import RedisGraphSnapshotCache
from .null_cache import NullGraphSnapshotCache

__all__ = ["NullGraphSnapshotCache", "RedisGraphSnapshotCache"]
