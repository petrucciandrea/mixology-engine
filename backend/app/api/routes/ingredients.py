"""Endpoint della dispensa."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_create_ingredient_use_case,
    get_delete_ingredient_use_case,
    get_get_ingredient_use_case,
    get_list_ingredients_use_case,
)
from app.api.schemas.ingredients import (
    FlavorDescriptorsOut,
    IngredientCreate,
    IngredientOut,
    IngredientPageOut,
)
from app.application.use_cases.ingredients import (
    CreateIngredientCommand,
    CreateIngredientUseCase,
    DeleteIngredientUseCase,
    GetIngredientUseCase,
    ListIngredientsUseCase,
)
from app.domain.entities import PhysicalProfile
from app.domain.enums import IngredientCategory
from app.domain.flavor import (
    AROMA_DESCRIPTORS,
    BASIC_TASTE_DESCRIPTORS,
    FLAVOR_DESCRIPTORS,
    FLAVOR_VECTOR_DIMENSION,
    TACTILE_DESCRIPTORS,
    FlavorProfile,
)

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get(
    "/flavor-descriptors",
    response_model=FlavorDescriptorsOut,
    summary="Il vocabolario organolettico accettato dall'API",
)
async def get_flavor_descriptors() -> FlavorDescriptorsOut:
    return FlavorDescriptorsOut(
        dimension=FLAVOR_VECTOR_DIMENSION,
        descriptors=list(FLAVOR_DESCRIPTORS),
        families={
            "basic_taste": list(BASIC_TASTE_DESCRIPTORS),
            "tactile": list(TACTILE_DESCRIPTORS),
            "aroma": list(AROMA_DESCRIPTORS),
        },
    )


@router.get("", response_model=IngredientPageOut, summary="Elenca gli ingredienti")
async def list_ingredients(
    use_case: Annotated[ListIngredientsUseCase, Depends(get_list_ingredients_use_case)],
    category: IngredientCategory | None = None,
    include_inactive: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> IngredientPageOut:
    page = await use_case.execute(
        category=category,
        active_only=not include_inactive,
        limit=limit,
        offset=offset,
    )
    return IngredientPageOut(
        items=[IngredientOut.from_entity(item) for item in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{ingredient_id}", response_model=IngredientOut, summary="Un ingrediente")
async def get_ingredient(
    ingredient_id: str,
    use_case: Annotated[GetIngredientUseCase, Depends(get_get_ingredient_use_case)],
) -> IngredientOut:
    return IngredientOut.from_entity(await use_case.execute(ingredient_id))


@router.post(
    "",
    response_model=IngredientOut,
    status_code=status.HTTP_201_CREATED,
    summary="Aggiunge un ingrediente alla dispensa",
)
async def create_ingredient(
    payload: IngredientCreate,
    use_case: Annotated[CreateIngredientUseCase, Depends(get_create_ingredient_use_case)],
) -> IngredientOut:
    # La conversione DTO → dominio avviene qui, nel layer che conosce
    # entrambi. `from_descriptors` rifiuta i nomi sconosciuti: un refuso
    # in un vocabolario di 32 termini diventa un 422 esplicito invece di
    # un descrittore silenziosamente ignorato.
    flavor = (
        FlavorProfile.from_descriptors(**payload.flavor_profile)
        if payload.flavor_profile is not None
        else None
    )
    ingredient = await use_case.execute(
        CreateIngredientCommand(
            name=payload.name,
            category=payload.category,
            physical_profile=PhysicalProfile(
                density_g_ml=payload.physical_profile.density_g_ml,
                brix=payload.physical_profile.brix,
                acidity=payload.physical_profile.acidity,
                abv=payload.physical_profile.abv,
            ),
            flavor_profile=flavor,
        )
    )
    return IngredientOut.from_entity(ingredient)


@router.delete(
    "/{ingredient_id}",
    response_model=IngredientOut,
    summary="Disattiva un ingrediente (non lo cancella)",
)
async def deactivate_ingredient(
    ingredient_id: str,
    use_case: Annotated[DeleteIngredientUseCase, Depends(get_delete_ingredient_use_case)],
) -> IngredientOut:
    return IngredientOut.from_entity(await use_case.execute(ingredient_id))
