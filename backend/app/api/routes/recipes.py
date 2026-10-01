"""Endpoint delle ricette salvate."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import (
    get_calculate_stored_balance_use_case,
    get_create_recipe_use_case,
    get_delete_recipe_use_case,
    get_get_recipe_use_case,
    get_list_recipes_use_case,
    get_optimize_stored_recipe_use_case,
    get_update_recipe_use_case,
)
from app.api.schemas.recipes import (
    BalanceOut,
    ConsumptionMinutes,
    RecipeIn,
    RecipeOut,
    RecipePageOut,
)
from app.api.schemas.solver import OptimizeStoredRequest, SolverResultOut
from app.application.use_cases.balancing import (
    CalculateStoredRecipeBalanceUseCase,
    DraftIngredient,
    DraftRecipe,
    OptimizeStoredRecipeUseCase,
)
from app.application.use_cases.recipes import (
    CreateRecipeUseCase,
    DeleteRecipeUseCase,
    GetRecipeUseCase,
    ListRecipesUseCase,
    UpdateRecipeUseCase,
)
from app.domain.services.serving_dilution import DEFAULT_CONSUMPTION_MINUTES

router = APIRouter(prefix="/recipes", tags=["recipes"])


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


@router.get("", response_model=RecipePageOut, summary="Elenca le ricette")
async def list_recipes(
    use_case: Annotated[ListRecipesUseCase, Depends(get_list_recipes_use_case)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RecipePageOut:
    page = await use_case.execute(limit=limit, offset=offset)
    return RecipePageOut(
        items=[RecipeOut.from_entity(item) for item in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "",
    response_model=RecipeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Salva una ricetta",
)
async def create_recipe(
    payload: RecipeIn,
    use_case: Annotated[CreateRecipeUseCase, Depends(get_create_recipe_use_case)],
) -> RecipeOut:
    recipe = await use_case.execute(_to_draft(payload), instructions=payload.instructions)
    return RecipeOut.from_entity(recipe)


@router.get("/{recipe_id}", response_model=RecipeOut, summary="Una ricetta")
async def get_recipe(
    recipe_id: str,
    use_case: Annotated[GetRecipeUseCase, Depends(get_get_recipe_use_case)],
) -> RecipeOut:
    return RecipeOut.from_entity(await use_case.execute(recipe_id))


@router.put("/{recipe_id}", response_model=RecipeOut, summary="Aggiorna il dosaggio")
async def update_recipe(
    recipe_id: str,
    payload: RecipeIn,
    use_case: Annotated[UpdateRecipeUseCase, Depends(get_update_recipe_use_case)],
) -> RecipeOut:
    recipe = await use_case.execute(
        recipe_id, _to_draft(payload), instructions=payload.instructions
    )
    return RecipeOut.from_entity(recipe)


@router.delete(
    "/{recipe_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # `response_class=Response` dice a FastAPI di non generare un corpo:
    # un 204 con payload viola la semantica HTTP, e senza questa riga il
    # framework rifiuta la rotta in fase di registrazione.
    response_class=Response,
    summary="Cancella una ricetta",
)
async def delete_recipe(
    recipe_id: str,
    use_case: Annotated[DeleteRecipeUseCase, Depends(get_delete_recipe_use_case)],
) -> Response:
    await use_case.execute(recipe_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{recipe_id}/balance",
    response_model=BalanceOut,
    summary="Profilo calcolato di una ricetta salvata",
)
async def get_recipe_balance(
    recipe_id: str,
    use_case: Annotated[
        CalculateStoredRecipeBalanceUseCase, Depends(get_calculate_stored_balance_use_case)
    ],
    consumption_minutes: ConsumptionMinutes = DEFAULT_CONSUMPTION_MINUTES,
) -> BalanceOut:
    result = await use_case.execute(recipe_id, consumption_minutes)
    return BalanceOut.from_result(result)


@router.post(
    "/{recipe_id}/optimize",
    response_model=SolverResultOut,
    summary="Ottimizza una ricetta salvata verso dei target",
)
async def optimize_recipe(
    recipe_id: str,
    payload: OptimizeStoredRequest,
    use_case: Annotated[OptimizeStoredRecipeUseCase, Depends(get_optimize_stored_recipe_use_case)],
) -> SolverResultOut:
    # L'ottimizzazione non salva: restituisce una proposta. Scriverla sulla
    # ricetta è una PUT separata, cioè una decisione di chi la legge.
    result = await use_case.execute(
        recipe_id,
        payload.target.to_domain(),
        payload.settings.to_domain() if payload.settings is not None else None,
    )
    return SolverResultOut.from_entity(result)
