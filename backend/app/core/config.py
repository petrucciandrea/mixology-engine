"""Configurazione centralizzata dell'applicazione.

Unico punto di lettura delle variabili d'ambiente: il resto del codice
(domain, application, infrastructure) non deve mai leggere `os.environ`
direttamente — dipende solo da questo oggetto `Settings`, iniettabile
e mockabile nei test.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Final
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Schemi "generici" di Postgres: senza driver esplicito SQLAlchemy
#: sceglierebbe psycopg2, che il progetto non installa.
_GENERIC_POSTGRES_SCHEMES: Final[frozenset[str]] = frozenset({"postgres", "postgresql"})
_ASYNCPG_SCHEME: Final[str] = "postgresql+asyncpg"


def normalize_database_url(url: str) -> str:
    """Rende utilizzabile da asyncpg un URL in formato libpq.

    I provider gestiti (Neon in produzione, ADR-0010) forniscono stringhe
    nel formato di libpq: `postgresql://…?sslmode=require&channel_binding=require`.
    Il dialetto asyncpg di SQLAlchemy passa i parametri della query come
    argomenti di `asyncpg.connect()`, che non conosce né `sslmode` né
    `channel_binding` e fallisce alla prima connessione. Qui:

    * lo schema generico diventa `postgresql+asyncpg`;
    * `sslmode` diventa `ssl`, con lo stesso valore: asyncpg accetta gli
      stessi nomi di modalità di libpq (`require`, `verify-full`, …);
    * `channel_binding` si toglie: asyncpg non lo supporta. La connessione
      resta cifrata e autenticata con SCRAM, senza il binding al canale.

    Un URL che è già asyncpg resta identico, quindi la funzione è
    idempotente e non tocca la configurazione di sviluppo.
    """
    parts = urlsplit(url)
    scheme = _ASYNCPG_SCHEME if parts.scheme in _GENERIC_POSTGRES_SCHEMES else parts.scheme
    if scheme != _ASYNCPG_SCHEME:
        return url

    query = [
        ("ssl" if key == "sslmode" else key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key != "channel_binding"
    ]
    return urlunsplit(parts._replace(scheme=scheme, query=urlencode(query)))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "local"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    project_name: str = "Mixology Engine"

    database_url: str

    #: Redis serve solo alla cache del grafo delle affinità. Senza, il
    #: composition root monta una cache nulla e il grafo si ricostruisce a
    #: ogni richiesta: è la configurazione dei piani gratuiti (ADR-0010),
    #: dove un servizio in più costa più di quanto la cache faccia
    #: risparmiare.
    redis_url: str | None = None

    #: Eco delle query SQL sul log. Separato da `debug` di proposito: in
    #: sviluppo serve il traceback dettagliato molto più spesso di quanto
    #: serva il dump di ogni SELECT, che rende i log illeggibili.
    echo_sql: bool = False

    #: Origini ammesse dal browser. Il frontend Next.js gira su 3000 in
    #: sviluppo; in produzione va valorizzata esplicitamente.
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("database_url")
    @classmethod
    def _asyncpg_database_url(cls, value: str) -> str:
        """App, Alembic e seed leggono tutti da qui: normalizzare in un solo
        punto significa poter incollare la stringa del provider così com'è."""
        return normalize_database_url(value)

    @field_validator("redis_url", mode="before")
    @classmethod
    def _blank_redis_url_means_absent(cls, value: object) -> object:
        """`REDIS_URL=` vuota vale "non configurato".

        Sui pannelli di deploy una variabile vuota è il modo naturale di
        dire che un servizio non c'è; trattarla come URL farebbe fallire
        il pool alla prima richiesta, lontano dalla causa.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    """Singleton cache-ato: evita di ri-parsare l'env ad ogni richiesta."""
    return Settings()
