"""Configurazione centralizzata dell'applicazione.

Unico punto di lettura delle variabili d'ambiente: il resto del codice
(domain, application, infrastructure) non deve mai leggere `os.environ`
direttamente — dipende solo da questo oggetto `Settings`, iniettabile
e mockabile nei test.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
