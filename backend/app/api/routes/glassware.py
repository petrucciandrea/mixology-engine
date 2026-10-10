"""Endpoint dei cataloghi di bicchieri."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_list_glassware_use_case
from app.api.schemas.glassware import GlasswareOut
from app.application.use_cases.glassware import ListGlasswareUseCase

router = APIRouter(prefix="/glassware", tags=["glassware"])


@router.get(
    "",
    response_model=list[GlasswareOut],
    summary="Cataloghi di bicchieri: misure, profili e ghiacci compatibili",
)
async def list_glassware(
    use_case: Annotated[ListGlasswareUseCase, Depends(get_list_glassware_use_case)],
) -> list[GlasswareOut]:
    return [GlasswareOut.from_entity(catalogue) for catalogue in use_case.execute()]
