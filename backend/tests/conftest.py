"""Fixture condivise per la suite di test.

Usiamo `httpx.ASGITransport` per parlare direttamente con l'app FastAPI
in-process (nessun server HTTP reale necessario) — ma le dipendenze
(DB, Redis) restano quelle vere, risolte via docker-compose network,
perché lo scopo di questo smoke test è verificare la comunicazione
reale tra i container.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
