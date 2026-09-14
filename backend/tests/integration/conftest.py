"""Fixture per i test che parlano con PostgreSQL.

Ogni test gira dentro una transazione che viene **annullata** alla fine:
il database torna esattamente com'era, i test non si influenzano a
vicenda e l'ordine di esecuzione non conta. È più veloce e più affidabile
di ricreare lo schema per ogni test.

`join_transaction_mode="create_savepoint"` è ciò che rende la cosa
possibile: senza, un `commit()` dentro il codice sotto test chiuderebbe
la transazione esterna e le scritture resterebbero nel database. Con
questa modalità la sessione apre un SAVEPOINT, e il commit del caso d'uso
lo rilascia senza toccare la transazione che lo racchiude.

L'engine è creato per singolo test con `NullPool`, e non condiviso come in
produzione. Non è una preferenza stilistica: pytest-asyncio apre un event
loop nuovo per ogni test, mentre le connessioni asyncpg restano legate al
loop su cui sono nate. Un pool condiviso fra test le riproporrebbe a un
loop diverso, e il secondo test della sessione fallirebbe con un errore
che non ha nulla a che vedere con ciò che sta verificando.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.domain.entities import Ingredient, PhysicalProfile
from app.domain.enums import IngredientCategory
from app.domain.flavor import FlavorProfile
from app.domain.repositories import IngredientRepository, RecipeRepository, UnitOfWork
from app.infrastructure.db.repositories import (
    SqlAlchemyIngredientRepository,
    SqlAlchemyRecipeRepository,
    SqlAlchemyUnitOfWork,
)

pytestmark = pytest.mark.integration


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


@pytest.fixture
def ingredient_repository(db_session: AsyncSession) -> IngredientRepository:
    return SqlAlchemyIngredientRepository(db_session)


@pytest.fixture
def recipe_repository(db_session: AsyncSession) -> RecipeRepository:
    return SqlAlchemyRecipeRepository(db_session)


@pytest.fixture
def unit_of_work(db_session: AsyncSession) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(db_session)


def make_ingredient(
    name: str,
    category: IngredientCategory = IngredientCategory.SPIRIT,
    *,
    abv: float = 0.40,
    brix: float = 0.0,
    acidity: float = 0.0,
    density_g_ml: float = 0.95,
    flavor: FlavorProfile | None = None,
) -> Ingredient:
    """Ingrediente con id e nome unici per test.

    Il nome porta un suffisso casuale perché la colonna ha un vincolo
    UNIQUE: senza, due test che creano "Rum" fallirebbero a seconda
    dell'ordine, e il rollback non basterebbe se girassero in parallelo.
    """
    unique = uuid.uuid4().hex[:8]
    return Ingredient(
        id=str(uuid.uuid4()),
        name=f"{name} {unique}",
        category=category,
        physical_profile=PhysicalProfile(
            density_g_ml=density_g_ml, brix=brix, acidity=acidity, abv=abv
        ),
        flavor_profile=flavor,
    )
