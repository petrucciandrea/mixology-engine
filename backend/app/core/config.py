"""Configurazione centralizzata dell'applicazione.

Unico punto di lettura delle variabili d'ambiente: il resto del codice
(domain, application, infrastructure) non deve mai leggere `os.environ`
direttamente — dipende solo da questo oggetto `Settings`, iniettabile
e mockabile nei test.
"""

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

    database_url: str
    redis_url: str

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_provider: str = "local"


@lru_cache
def get_settings() -> Settings:
    """Singleton cache-ato: evita di ri-parsare l'env ad ogni richiesta."""
    return Settings()  # type: ignore[call-arg]  # valori richiesti letti da env
