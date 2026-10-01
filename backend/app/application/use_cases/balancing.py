"""Casi d'uso di bilanciamento: calcolare un profilo, ottimizzare una ricetta.

Il caso d'uso è il punto in cui si compone: carica gli ingredienti dal
repository (attraverso la porta, non attraverso SQLAlchemy), costruisce
l'aggregate di dominio, invoca il servizio di dominio o il solver e
restituisce un risultato. Non conosce HTTP e non conosce SQL.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.application.solver.balancing_solver import BalancingSolver
from app.application.solver.models import SolverResult, SolverSettings, TargetProfile
from app.domain.balance import BalanceProfile, ServingProfile
from app.domain.entities import Ingredient, Recipe, RecipeIngredient
from app.domain.enums import DilutionMethod, GlassType, RecipeFamily, ServingIce
from app.domain.errors import EntityNotFoundError, InvalidRecipeError
from app.domain.repositories import IngredientRepository, RecipeRepository
from app.domain.services.balance_calculator import calculate_balance
from app.domain.services.glassware import GlassFit, assess_glass_fit
from app.domain.services.serving_dilution import (
    DEFAULT_CONSUMPTION_MINUTES,
    calculate_serving_profile,
)

#: Prefisso degli id delle ricette non persistite. Una ricetta di lavoro
#: è comunque un aggregate valido — deve avere un'identità — ma l'id
#: dichiara che non esiste una riga corrispondente nel database.
DRAFT_ID_PREFIX = "draft:"


@dataclass(frozen=True, slots=True)
class DraftIngredient:
    """Una dose in una ricetta di lavoro: riferimento all'ingrediente e volume."""

    ingredient_id: str
    volume_ml: float


@dataclass(frozen=True, slots=True)
class DraftRecipe:
    """Ricetta non persistita, così come arriva dall'editor.

    Esiste perché il caso d'uso più frequente dell'applicazione — muovere
    uno slider e vedere il profilo aggiornarsi — non deve richiedere il
    salvataggio di nulla. Il dominio lavora comunque su una `Recipe`
    valida: la conversione avviene qui.
    """

    name: str
    dilution_method: DilutionMethod
    serving_ice: ServingIce
    ingredients: tuple[DraftIngredient, ...]
    glass: GlassType | None = None
    family: RecipeFamily | None = None

    def __post_init__(self) -> None:
        if not self.ingredients:
            raise InvalidRecipeError("a recipe must contain at least one ingredient")


class RecipeAssembler:
    """Trasforma una ricetta di lavoro in un aggregate di dominio.

    Carica gli ingredienti in **una sola query** (`get_many`): il numero
    di ingredienti è noto in anticipo, e pagare un round-trip per dose
    sarebbe un N+1 evitabile.
    """

    def __init__(self, ingredients: IngredientRepository) -> None:
        self._ingredients = ingredients

    async def assemble(self, draft: DraftRecipe, recipe_id: str | None = None) -> Recipe:
        wanted_ids = [item.ingredient_id for item in draft.ingredients]
        found = await self._ingredients.get_many(wanted_ids)
        by_id: dict[str, Ingredient] = {ingredient.id: ingredient for ingredient in found}

        missing = [wanted for wanted in wanted_ids if wanted not in by_id]
        if missing:
            # Si segnala il primo mancante: l'errore deve identificare una
            # causa precisa, non elencare un insieme che il chiamante
            # dovrebbe poi interpretare.
            raise EntityNotFoundError("Ingredient", missing[0])

        return Recipe(
            id=recipe_id or f"{DRAFT_ID_PREFIX}{uuid.uuid4()}",
            name=draft.name,
            dilution_method=draft.dilution_method,
            serving_ice=draft.serving_ice,
            glass=draft.glass,
            family=draft.family,
            ingredients=tuple(
                RecipeIngredient(ingredient=by_id[item.ingredient_id], volume_ml=item.volume_ml)
                for item in draft.ingredients
            ),
        )


@dataclass(frozen=True, slots=True)
class BalanceResult:
    """Ricetta, profilo da preparazione, profilo da servizio e bicchiere.

    `serving` è `None` per una ricetta servita senza ghiaccio; `glass_fit`
    per una ricetta senza bicchiere, o con un bicchiere senza capienza nota.
    """

    recipe: Recipe
    profile: BalanceProfile
    serving: ServingProfile | None
    glass_fit: GlassFit | None


def _balance_result(recipe: Recipe, consumption_minutes: float) -> BalanceResult:
    profile = calculate_balance(recipe)
    return BalanceResult(
        recipe=recipe,
        profile=profile,
        serving=calculate_serving_profile(recipe, profile, consumption_minutes),
        glass_fit=assess_glass_fit(recipe, profile.final_volume_ml),
    )


class CalculateBalanceUseCase:
    """Calcola il profilo di una ricetta di lavoro, senza persistere nulla."""

    def __init__(self, ingredients: IngredientRepository) -> None:
        self._assembler = RecipeAssembler(ingredients)

    async def execute(
        self, draft: DraftRecipe, consumption_minutes: float = DEFAULT_CONSUMPTION_MINUTES
    ) -> BalanceResult:
        recipe = await self._assembler.assemble(draft)
        # Nessun `to_thread` qui: il calcolo è una manciata di somme su
        # pochi ingredienti, dell'ordine dei microsecondi. Spostarlo su un
        # thread costerebbe più della sua esecuzione.
        return _balance_result(recipe, consumption_minutes)


class CalculateStoredRecipeBalanceUseCase:
    """Calcola il profilo di una ricetta salvata."""

    def __init__(self, recipes: RecipeRepository) -> None:
        self._recipes = recipes

    async def execute(
        self, recipe_id: str, consumption_minutes: float = DEFAULT_CONSUMPTION_MINUTES
    ) -> BalanceResult:
        recipe = await self._recipes.get(recipe_id)
        if recipe is None:
            raise EntityNotFoundError("Recipe", recipe_id)
        return _balance_result(recipe, consumption_minutes)


class OptimizeRecipeUseCase:
    """Ottimizza i volumi di una ricetta di lavoro verso i target richiesti.

    ADR-002: SLSQP è CPU-bound e gira per decine di millisecondi con
    ripartenze multiple. Eseguirlo direttamente nella coroutine bloccherebbe
    l'event loop per tutta la durata, mettendo in coda ogni altra richiesta
    del processo — inclusi gli health check. `asyncio.to_thread` lo sposta
    sul thread pool: SciPy rilascia il GIL nelle routine numeriche, quindi
    il parallelismo è reale e non solo apparente.
    """

    def __init__(self, ingredients: IngredientRepository, solver: BalancingSolver) -> None:
        self._assembler = RecipeAssembler(ingredients)
        self._solver = solver

    async def execute(
        self,
        draft: DraftRecipe,
        target: TargetProfile,
        settings: SolverSettings | None = None,
    ) -> SolverResult:
        recipe = await self._assembler.assemble(draft)
        return await asyncio.to_thread(self._solver.solve, recipe, target, settings)


class OptimizeStoredRecipeUseCase:
    """Ottimizza una ricetta salvata, restituendo il risultato senza salvarlo.

    Il salvataggio è un'azione separata e deliberata: ottimizzare non deve
    sovrascrivere la ricetta dell'autore come effetto collaterale di una
    consultazione.
    """

    def __init__(self, recipes: RecipeRepository, solver: BalancingSolver) -> None:
        self._recipes = recipes
        self._solver = solver

    async def execute(
        self,
        recipe_id: str,
        target: TargetProfile,
        settings: SolverSettings | None = None,
    ) -> SolverResult:
        recipe = await self._recipes.get(recipe_id)
        if recipe is None:
            raise EntityNotFoundError("Recipe", recipe_id)
        return await asyncio.to_thread(self._solver.solve, recipe, target, settings)


def draft_from_ingredients(
    name: str,
    dilution_method: DilutionMethod,
    serving_ice: ServingIce,
    items: Sequence[tuple[str, float]],
) -> DraftRecipe:
    """Helper di costruzione, usato soprattutto dai test e dagli script di seed."""
    return DraftRecipe(
        name=name,
        dilution_method=dilution_method,
        serving_ice=serving_ice,
        ingredients=tuple(
            DraftIngredient(ingredient_id=ingredient_id, volume_ml=volume)
            for ingredient_id, volume in items
        ),
    )
