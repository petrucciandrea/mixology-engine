"""Casi d'uso sulla dispensa degli ingredienti."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace

from app.domain.entities import Ingredient, PhysicalProfile
from app.domain.enums import IngredientCategory
from app.domain.errors import DuplicateEntityError, EntityNotFoundError
from app.domain.flavor import FlavorProfile
from app.domain.repositories import IngredientRepository, UnitOfWork


@dataclass(frozen=True, slots=True)
class CreateIngredientCommand:
    name: str
    category: IngredientCategory
    physical_profile: PhysicalProfile
    flavor_profile: FlavorProfile | None = None


@dataclass(frozen=True, slots=True)
class IngredientPage:
    """Una pagina di risultati, con il totale per costruire la paginazione."""

    items: list[Ingredient]
    total: int
    limit: int
    offset: int


class CreateIngredientUseCase:
    def __init__(self, ingredients: IngredientRepository, uow: UnitOfWork) -> None:
        self._ingredients = ingredients
        self._uow = uow

    async def execute(self, command: CreateIngredientCommand) -> Ingredient:
        # Il nome è la chiave naturale: due bottiglie con lo stesso nome
        # sarebbero indistinguibili per chi compone una ricetta. Il
        # controllo qui produce un errore di dominio leggibile; il vincolo
        # UNIQUE sul database resta la garanzia contro le corse fra
        # richieste concorrenti.
        if await self._ingredients.get_by_name(command.name) is not None:
            raise DuplicateEntityError("Ingredient", "name", command.name)

        ingredient = Ingredient(
            id=str(uuid.uuid4()),
            name=command.name,
            category=command.category,
            physical_profile=command.physical_profile,
            flavor_profile=command.flavor_profile,
        )
        created = await self._ingredients.add(ingredient)
        await self._uow.commit()
        return created


class GetIngredientUseCase:
    def __init__(self, ingredients: IngredientRepository) -> None:
        self._ingredients = ingredients

    async def execute(self, ingredient_id: str) -> Ingredient:
        ingredient = await self._ingredients.get(ingredient_id)
        if ingredient is None:
            raise EntityNotFoundError("Ingredient", ingredient_id)
        return ingredient


class ListIngredientsUseCase:
    def __init__(self, ingredients: IngredientRepository) -> None:
        self._ingredients = ingredients

    async def execute(
        self,
        *,
        category: IngredientCategory | None = None,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> IngredientPage:
        items = await self._ingredients.list(
            category=category, active_only=active_only, limit=limit, offset=offset
        )
        total = await self._ingredients.count(category=category, active_only=active_only)
        return IngredientPage(items=items, total=total, limit=limit, offset=offset)


class DeleteIngredientUseCase:
    """Disattiva un ingrediente invece di cancellarlo.

    Cancellare davvero romperebbe le ricette che lo usano: un ingrediente
    uscito dal listino resta parte della storia dei drink già composti.
    `is_active = False` lo toglie dalle liste senza perdere i riferimenti.
    """

    def __init__(self, ingredients: IngredientRepository, uow: UnitOfWork) -> None:
        self._ingredients = ingredients
        self._uow = uow

    async def execute(self, ingredient_id: str) -> Ingredient:
        ingredient = await self._ingredients.get(ingredient_id)
        if ingredient is None:
            raise EntityNotFoundError("Ingredient", ingredient_id)

        deactivated = replace(ingredient, is_active=False)
        saved = await self._ingredients.save(deactivated)
        await self._uow.commit()
        return saved
