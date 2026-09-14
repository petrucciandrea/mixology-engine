"""Casi d'uso sulle ricette salvate."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace

from app.application.use_cases.balancing import DraftRecipe, RecipeAssembler
from app.domain.entities import Recipe
from app.domain.errors import EntityNotFoundError
from app.domain.repositories import IngredientRepository, RecipeRepository, UnitOfWork


@dataclass(frozen=True, slots=True)
class RecipePage:
    items: list[Recipe]
    total: int
    limit: int
    offset: int


class CreateRecipeUseCase:
    """Salva una ricetta, risolvendo i riferimenti agli ingredienti.

    L'assemblaggio passa dallo stesso `RecipeAssembler` usato dal
    bilanciamento: una ricetta salvata e una di lavoro attraversano le
    stesse validazioni, quindi non può esistere nel database una ricetta
    che il dominio rifiuterebbe.
    """

    def __init__(
        self,
        recipes: RecipeRepository,
        ingredients: IngredientRepository,
        uow: UnitOfWork,
    ) -> None:
        self._recipes = recipes
        self._assembler = RecipeAssembler(ingredients)
        self._uow = uow

    async def execute(self, draft: DraftRecipe, instructions: str | None = None) -> Recipe:
        recipe = await self._assembler.assemble(draft, recipe_id=str(uuid.uuid4()))
        if instructions is not None:
            recipe = replace(recipe, instructions=instructions)
        created = await self._recipes.add(recipe)
        await self._uow.commit()
        return created


class GetRecipeUseCase:
    def __init__(self, recipes: RecipeRepository) -> None:
        self._recipes = recipes

    async def execute(self, recipe_id: str) -> Recipe:
        recipe = await self._recipes.get(recipe_id)
        if recipe is None:
            raise EntityNotFoundError("Recipe", recipe_id)
        return recipe


class ListRecipesUseCase:
    def __init__(self, recipes: RecipeRepository) -> None:
        self._recipes = recipes

    async def execute(self, *, limit: int = 50, offset: int = 0) -> RecipePage:
        items = await self._recipes.list(limit=limit, offset=offset)
        total = await self._recipes.count()
        return RecipePage(items=items, total=total, limit=limit, offset=offset)


class UpdateRecipeUseCase:
    """Sostituisce il dosaggio di una ricetta esistente, conservandone l'identità.

    È il caso d'uso che rende utile l'ottimizzatore: si ottimizza, si
    guarda il risultato, e solo se convince lo si scrive sulla ricetta.
    """

    def __init__(
        self,
        recipes: RecipeRepository,
        ingredients: IngredientRepository,
        uow: UnitOfWork,
    ) -> None:
        self._recipes = recipes
        self._assembler = RecipeAssembler(ingredients)
        self._uow = uow

    async def execute(
        self, recipe_id: str, draft: DraftRecipe, instructions: str | None = None
    ) -> Recipe:
        existing = await self._recipes.get(recipe_id)
        if existing is None:
            raise EntityNotFoundError("Recipe", recipe_id)

        updated = await self._assembler.assemble(draft, recipe_id=recipe_id)
        updated = replace(
            updated,
            instructions=instructions if instructions is not None else existing.instructions,
        )
        saved = await self._recipes.save(updated)
        await self._uow.commit()
        return saved


class DeleteRecipeUseCase:
    def __init__(self, recipes: RecipeRepository, uow: UnitOfWork) -> None:
        self._recipes = recipes
        self._uow = uow

    async def execute(self, recipe_id: str) -> None:
        deleted = await self._recipes.delete(recipe_id)
        if not deleted:
            raise EntityNotFoundError("Recipe", recipe_id)
        await self._uow.commit()
