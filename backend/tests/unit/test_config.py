"""Lettura della configurazione: i valori che arrivano dai pannelli di deploy."""

from __future__ import annotations

import pytest

from app.core.config import Settings, normalize_database_url

LOCAL_DATABASE_URL = "postgresql+asyncpg://mixology:pw@db:5432/mixology_engine"

#: La stringa di connessione così come la mostra il pannello di Neon.
NEON_URL = (
    "postgresql://app:s3cr%40t@ep-cool-name-123456.eu-central-1.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)


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


class TestDatabaseUrl:
    def test_a_neon_url_becomes_an_asyncpg_url(self) -> None:
        """Driver esplicito, `sslmode` tradotto in `ssl`, `channel_binding`
        rimosso: sono i due parametri che `asyncpg.connect()` rifiuta."""
        assert normalize_database_url(NEON_URL) == (
            "postgresql+asyncpg://app:s3cr%40t@ep-cool-name-123456.eu-central-1.aws.neon.tech"
            "/neondb?ssl=require"
        )

    def test_the_short_postgres_scheme_is_accepted(self) -> None:
        assert normalize_database_url("postgres://u:p@host:5432/db") == (
            "postgresql+asyncpg://u:p@host:5432/db"
        )

    @pytest.mark.parametrize(
        "url",
        [
            LOCAL_DATABASE_URL,
            "postgresql+asyncpg://u:p@host/db?ssl=require",
        ],
    )
    def test_an_asyncpg_url_is_left_untouched(self, url: str) -> None:
        assert normalize_database_url(url) == url

    def test_settings_apply_the_normalization(self) -> None:
        """Il punto è questo: app, Alembic e seed leggono tutti da
        `Settings`, quindi sul pannello si incolla la stringa di Neon così
        com'è."""
        assert make_settings(database_url=NEON_URL).database_url == normalize_database_url(NEON_URL)
