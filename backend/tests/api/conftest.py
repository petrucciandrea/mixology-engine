"""Fixture per i test HTTP.

Il client parla con l'applicazione **reale** via `ASGITransport`, senza
alzare un server: stesso routing, stessa validazione, stessi gestori di
errore, zero latenza di rete.

L'unica dipendenza sostituita è la sessione del database, rimpiazzata con
quella transazionale dei test. La sostituzione avviene attraverso
`dependency_overrides`, cioè il meccanismo previsto da FastAPI: i
repository, i casi d'uso e il solver restano quelli di produzione, e ciò
che il test verifica è l'intera catena, non un mock di se stessa.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_redis, get_session
from app.core.config import get_settings
from app.main import create_app

pytestmark = pytest.mark.api

API = "/api/v1"

#: Indice del database Redis riservato ai test.
#:
#: La cache del grafo e' scritta e riletta davvero durante i test dell'API —
#: e' proprio quel percorso che si vuole verificare — ma i test annullano le
#: proprie scritture sul database, quindi la stessa impronta puo' ripetersi
#: fra test diversi. Senza un database separato e svuotato, un grafo messo
#: in cache da un test verrebbe servito al successivo, che ha una dispensa
#: diversa: i test passerebbero o fallirebbero a seconda dell'ordine.
TEST_REDIS_DB = 15


def _test_redis_url() -> str:
    base = get_settings().redis_url.rsplit("/", 1)[0]
    return f"{base}/{TEST_REDIS_DB}"


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    created = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        yield created
    finally:
        await created.dispose()


@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    """Client Redis per test, con il proprio pool e il proprio database.

    Il pool e' per test, non condiviso, per la stessa ragione per cui lo e'
    l'engine: pytest-asyncio apre un event loop nuovo a ogni test e le
    connessioni restano legate al loop su cui sono nate.
    """
    client = Redis.from_url(_test_redis_url(), decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession, redis_client: Redis
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_redis() -> AsyncGenerator[Redis, None]:
        yield redis_client

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_redis] = override_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_without_redis(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """L'app come gira in produzione sui piani gratuiti: Redis non configurato.

    `get_redis` restituisce `None` esattamente come farebbe con
    `REDIS_URL` vuota; il resto della catena — composition root, cache
    nulla, health check — resta quello reale.
    """
    app = create_app()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_redis() -> AsyncGenerator[None, None]:
        yield None

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_redis] = override_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def rum_id(client: AsyncClient) -> str:
    return await create_ingredient(
        client,
        name="Rum Bianco",
        category="SPIRIT",
        abv=0.40,
        brix=0.0,
        acidity=0.0,
        density_g_ml=0.95,
        flavor={"alcohol_heat": 0.6, "tropical_fruit": 0.3},
    )


@pytest_asyncio.fixture
async def lime_id(client: AsyncClient) -> str:
    return await create_ingredient(
        client,
        name="Succo di Lime",
        category="JUICE",
        abv=0.0,
        brix=1.7,
        acidity=6.0,
        density_g_ml=1.03,
        flavor={"sour": 0.95, "citrus": 0.9},
    )


@pytest_asyncio.fixture
async def syrup_id(client: AsyncClient) -> str:
    return await create_ingredient(
        client,
        name="Sciroppo 1:1",
        category="SYRUP",
        abv=0.0,
        brix=50.0,
        acidity=0.0,
        density_g_ml=1.23,
        flavor={"sweet": 1.0},
    )


async def create_ingredient(
    client: AsyncClient,
    *,
    name: str,
    category: str,
    abv: float,
    brix: float,
    acidity: float,
    density_g_ml: float,
    flavor: dict[str, float] | None = None,
) -> str:
    """Crea un ingrediente via API e restituisce il suo id.

    Il nome porta un suffisso univoco: la colonna ha un vincolo UNIQUE e i
    test devono poter girare più volte sullo stesso database.
    """
    payload: dict[str, Any] = {
        "name": f"{name} {uuid.uuid4().hex[:8]}",
        "category": category,
        "physical_profile": {
            "density_g_ml": density_g_ml,
            "brix": brix,
            "acidity": acidity,
            "abv": abv,
        },
    }
    if flavor is not None:
        payload["flavor_profile"] = flavor

    response = await client.post(f"{API}/ingredients", json=payload)
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def daiquiri_payload(
    rum_id: str, lime_id: str, syrup_id: str, volumes: tuple[float, float, float]
) -> dict[str, Any]:
    return {
        "name": "Daiquiri",
        "dilution_method": "SHAKEN",
        "serving_ice": "NONE",
        "ingredients": [
            {"ingredient_id": rum_id, "volume_ml": volumes[0]},
            {"ingredient_id": lime_id, "volume_ml": volumes[1]},
            {"ingredient_id": syrup_id, "volume_ml": volumes[2]},
        ],
    }
