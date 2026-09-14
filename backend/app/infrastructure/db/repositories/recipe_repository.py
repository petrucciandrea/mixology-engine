"""Repository SQLAlchemy per le ricette."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities import Recipe

from ..mappers import recipe_to_domain, recipe_to_row
from ..models import RecipeIngredientModel, RecipeModel


class SqlAlchemyRecipeRepository:
    """Implementazione della porta `RecipeRepository`.

    Una ricetta è un aggregate: viene sempre caricata completa, con i suoi
    ingredienti dosati e gli ingredienti a cui si riferiscono. Il
    caricamento eager (`selectinload` + `joinedload` sulla relationship)
    costa due query fisse invece di una per dose: senza, elencare venti
    ricette da tre ingredienti significherebbe sessanta query.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _full_recipe_query(self) -> Select[tuple[RecipeModel]]:
        return select(RecipeModel).options(
            selectinload(RecipeModel.ingredients).joinedload(RecipeIngredientModel.ingredient)
        )

    async def get(self, recipe_id: str) -> Recipe | None:
        statement = self._full_recipe_query().where(RecipeModel.id == recipe_id)
        row = (await self._session.execute(statement)).unique().scalar_one_or_none()
        return recipe_to_domain(row) if row is not None else None

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[Recipe]:
        statement = self._full_recipe_query().order_by(RecipeModel.name).limit(limit).offset(offset)
        rows = (await self._session.execute(statement)).unique().scalars().all()
        return [recipe_to_domain(row) for row in rows]

    async def count(self) -> int:
        statement = select(func.count()).select_from(RecipeModel)
        return int((await self._session.execute(statement)).scalar_one())

    async def add(self, recipe: Recipe) -> Recipe:
        row = recipe_to_row(recipe)
        self._session.add(row)
        await self._session.flush()
        return await self._reload(recipe.id)

    async def save(self, recipe: Recipe) -> Recipe:
        statement = self._full_recipe_query().where(RecipeModel.id == recipe.id)
        existing = (await self._session.execute(statement)).unique().scalar_one_or_none()

        if existing is not None:
            # Il dosaggio precedente va cancellato **e scaricato** prima di
            # inserire quello nuovo. In un unico flush SQLAlchemy emette gli
            # INSERT prima dei DELETE, e il vincolo UNIQUE
            # (recipe_id, ingredient_id) scatta su un ingrediente che compare
            # sia nella vecchia sia nella nuova versione — cioe' nel caso
            # piu' comune, quello di una ricetta ribilanciata.
            existing.ingredients.clear()
            await self._session.flush()

        row = recipe_to_row(recipe, existing)
        if existing is None:
            self._session.add(row)
        await self._session.flush()
        return await self._reload(recipe.id)

    async def delete(self, recipe_id: str) -> bool:
        row = await self._session.get(RecipeModel, recipe_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True

    async def _reload(self, recipe_id: str) -> Recipe:
        """Rilegge l'aggregate dopo la scrittura.

        Serve perché le righe di dosaggio appena create non hanno ancora
        caricato l'ingrediente a cui puntano: senza una rilettura esplicita
        il mapper innescherebbe una lazy load in contesto asincrono, che
        SQLAlchemy rifiuta.
        """
        reloaded = await self.get(recipe_id)
        if reloaded is None:  # pragma: no cover - incoerenza impossibile dopo un flush
            raise RuntimeError(f"recipe '{recipe_id}' vanished right after being written")
        return reloaded
