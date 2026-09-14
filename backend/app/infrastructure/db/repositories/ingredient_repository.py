"""Repository SQLAlchemy per gli ingredienti."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Ingredient
from app.domain.enums import IngredientCategory

from ..mappers import ingredient_to_domain, ingredient_to_row
from ..models import IngredientModel

#: I filtri si applicano sia alla query di elenco sia a quella di conteggio,
#: che hanno tipo di risultato diverso: il TypeVar preserva il tipo esatto
#: della Select invece di degradarlo, cosi' MyPy continua a verificare a valle.
_SelectT = TypeVar("_SelectT", bound=Select[Any])


class SqlAlchemyIngredientRepository:
    """Implementazione della porta `IngredientRepository`.

    Ogni metodo restituisce **entità di dominio**, mai righe ORM: gli
    oggetti SQLAlchemy non escono da questo layer, e un caso d'uso non ha
    modo di innescare accidentalmente una lazy load a valle.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, ingredient_id: str) -> Ingredient | None:
        row = await self._session.get(IngredientModel, ingredient_id)
        return ingredient_to_domain(row) if row is not None else None

    async def get_by_name(self, name: str) -> Ingredient | None:
        statement = select(IngredientModel).where(IngredientModel.name == name)
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return ingredient_to_domain(row) if row is not None else None

    async def get_many(self, ingredient_ids: Sequence[str]) -> list[Ingredient]:
        if not ingredient_ids:
            return []
        statement = select(IngredientModel).where(IngredientModel.id.in_(list(ingredient_ids)))
        rows = (await self._session.execute(statement)).scalars().all()
        return [ingredient_to_domain(row) for row in rows]

    async def list(
        self,
        *,
        category: IngredientCategory | None = None,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Ingredient]:
        statement = select(IngredientModel).order_by(IngredientModel.name)
        statement = self._apply_filters(statement, category, active_only)
        statement = statement.limit(limit).offset(offset)
        rows = (await self._session.execute(statement)).scalars().all()
        return [ingredient_to_domain(row) for row in rows]

    async def count(
        self,
        *,
        category: IngredientCategory | None = None,
        active_only: bool = True,
    ) -> int:
        statement = select(func.count()).select_from(IngredientModel)
        statement = self._apply_filters(statement, category, active_only)
        return int((await self._session.execute(statement)).scalar_one())

    async def add(self, ingredient: Ingredient) -> Ingredient:
        row = ingredient_to_row(ingredient)
        self._session.add(row)
        # `flush` e non `commit`: la riga raggiunge il database — quindi i
        # vincoli scattano subito e gli errori sono attribuibili a questa
        # operazione — ma la transazione resta aperta, e a chiuderla è il
        # caso d'uso attraverso la UnitOfWork.
        await self._session.flush()
        return ingredient_to_domain(row)

    async def save(self, ingredient: Ingredient) -> Ingredient:
        existing = await self._session.get(IngredientModel, ingredient.id)
        row = ingredient_to_row(ingredient, existing)
        if existing is None:
            self._session.add(row)
        await self._session.flush()
        return ingredient_to_domain(row)

    async def delete(self, ingredient_id: str) -> bool:
        row = await self._session.get(IngredientModel, ingredient_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True

    @staticmethod
    def _apply_filters(
        statement: _SelectT,
        category: IngredientCategory | None,
        active_only: bool,
    ) -> _SelectT:
        if category is not None:
            statement = statement.where(IngredientModel.category == category)
        if active_only:
            statement = statement.where(IngredientModel.is_active.is_(True))
        return statement
