"""Smoke test dell'ambiente Docker Compose.

Obiettivo: eseguito via `make test` (cioè dentro il container `backend`,
sulla rete Docker Compose), questo test conferma che:
1. la configurazione viene letta correttamente dall'env;
2. l'app FastAPI si avvia senza errori di wiring;
3. il container backend comunica realmente con `db` (Postgres/pgvector)
   e con `redis` — non un mock, la connessione TCP avviene per davvero.

Se questo file passa dopo `docker compose up`, l'intero stack è pronto
per lo sviluppo del domain layer.
"""

import pytest
from httpx import AsyncClient

from app.core.config import get_settings


def test_settings_load_from_env() -> None:
    """La configurazione deve essere popolata (fail-fast se manca .env)."""
    settings = get_settings()
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.redis_url.startswith("redis://")


@pytest.mark.asyncio
async def test_root_endpoint_responds(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"service": "mixology-engine", "status": "running"}


@pytest.mark.asyncio
async def test_health_endpoint_reports_ok_when_stack_is_up(client: AsyncClient) -> None:
    """Verifica end-to-end: DB e Redis devono essere realmente raggiungibili.

    Se questo test fallisce con status="degraded", controlla:
    - `docker compose ps` (i container db/redis sono healthy?)
    - le variabili DATABASE_URL / REDIS_URL nel container backend
    """
    response = await client.get("/health")
    body = response.json()

    assert response.status_code == 200
    assert body["database"] == "connected", "Postgres non raggiungibile dal container backend"
    assert body["redis"] == "connected", "Redis non raggiungibile dal container backend"
    assert body["status"] == "ok"
