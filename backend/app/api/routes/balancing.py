"""Endpoint di calcolo e ottimizzazione su ricette non salvate.

Sono gli endpoint che regge l'editor: muovere uno slider e vedere il
profilo aggiornarsi non deve richiedere di salvare nulla, altrimenti ogni
tentativo lascerebbe una riga nel database.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_calculate_balance_use_case, get_optimize_recipe_use_case
from app.api.schemas.recipes import BalanceOut, ConsumptionMinutes, RecipeIn
from app.api.schemas.solver import OptimizeRequest, SolverResultOut
from app.application.use_cases.balancing import (
    CalculateBalanceUseCase,
    DraftIngredient,
    DraftRecipe,
    OptimizeRecipeUseCase,
)
from app.domain.services.serving_dilution import DEFAULT_CONSUMPTION_MINUTES

router = APIRouter(tags=["balancing"])


def _to_draft(payload: RecipeIn) -> DraftRecipe:
    return DraftRecipe(
        name=payload.name,
        dilution_method=payload.dilution_method,
        serving_ice=payload.serving_ice,
        glass=payload.glass,
        family=payload.family,
        ingredients=tuple(
            DraftIngredient(ingredient_id=item.ingredient_id, volume_ml=item.volume_ml)
            for item in payload.ingredients
        ),
    )


@router.post(
    "/balance",
    response_model=BalanceOut,
    summary="Calcola il profilo di una ricetta, senza salvarla",
)
async def calculate_balance(
    payload: RecipeIn,
    use_case: Annotated[CalculateBalanceUseCase, Depends(get_calculate_balance_use_case)],
    consumption_minutes: ConsumptionMinutes = DEFAULT_CONSUMPTION_MINUTES,
) -> BalanceOut:
    result = await use_case.execute(_to_draft(payload), consumption_minutes)
    return BalanceOut.from_result(result)


@router.post(
    "/optimize",
    response_model=SolverResultOut,
    summary="Trova i volumi che avvicinano una ricetta ai target",
)
async def optimize(
    payload: OptimizeRequest,
    use_case: Annotated[OptimizeRecipeUseCase, Depends(get_optimize_recipe_use_case)],
) -> SolverResultOut:
    result = await use_case.execute(
        _to_draft(payload.recipe),
        payload.target.to_domain(),
        payload.settings.to_domain() if payload.settings is not None else None,
    )
    return SolverResultOut.from_entity(result)
