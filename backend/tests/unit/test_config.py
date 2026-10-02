"""Lettura della configurazione: i valori che arrivano dai pannelli di deploy."""

from __future__ import annotations

from app.core.config import Settings

LOCAL_DATABASE_URL = "postgresql+asyncpg://mixology:pw@db:5432/mixology_engine"


def make_settings(
    *, database_url: str = LOCAL_DATABASE_URL, redis_url: str = "redis://redis:6379/0"
) -> Settings:
    # `_env_file=None`: il test non deve dipendere da un `.env` presente
    # sulla macchina; i valori espliciti vincono comunque sull'ambiente.
    return Settings(_env_file=None, database_url=database_url, redis_url=redis_url)


class TestRedisUrl:
    def test_an_empty_value_disables_redis(self) -> None:
        """Su un pannello di deploy "variabile vuota" è il modo naturale per
        dire "non c'è": va letto come assenza, non come URL non valido."""
        assert make_settings(redis_url="").redis_url is None

    def test_a_configured_value_is_kept(self) -> None:
        assert make_settings().redis_url == "redis://redis:6379/0"
