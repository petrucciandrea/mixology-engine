"""Endpoint del catalogo dei bicchieri."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_list_glassware_use_case
from app.api.schemas.glassware import GlassOut
from app.application.use_cases.glassware import ListGlasswareUseCase

router = APIRouter(prefix="/glassware", tags=["glassware"])


@router.get(
    "",
    response_model=list[GlassOut],
    summary="Bicchieri con capienza e ghiacci compatibili",
)
async def list_glassware(
    use_case: Annotated[ListGlasswareUseCase, Depends(get_list_glassware_use_case)],
) -> list[GlassOut]:
    return [GlassOut.from_entity(spec) for spec in use_case.execute()]
