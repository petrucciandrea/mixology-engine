"""Configurazione centralizzata dell'applicazione.

Unico punto di lettura delle variabili d'ambiente: il resto del codice
(domain, application, infrastructure) non deve mai leggere `os.environ`
direttamente — dipende solo da questo oggetto `Settings`, iniettabile
e mockabile nei test.
"""

from __future__ import annotations

from functools import lru_cache

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
    redis_url: str

    #: Eco delle query SQL sul log. Separato da `debug` di proposito: in
    #: sviluppo serve il traceback dettagliato molto più spesso di quanto
    #: serva il dump di ogni SELECT, che rende i log illeggibili.
    echo_sql: bool = False

    #: Origini ammesse dal browser. Il frontend Next.js gira su 3000 in
    #: sviluppo; in produzione va valorizzata esplicitamente.
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]


@lru_cache
def get_settings() -> Settings:
    """Singleton cache-ato: evita di ri-parsare l'env ad ogni richiesta."""
    return Settings()
