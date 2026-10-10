"""DTO del catalogo dei bicchieri."""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.enums import GlassType, ServingIce
from app.domain.services.glassware import GlassSpec


class GlassOut(BaseModel):
    """Un bicchiere: capienza (`null` se ignota) e ghiacci che ci entrano.

    L'editor usa `compatible_ice` per disabilitare i ghiacci che il
    bicchiere non accoglie, invece di rifare la geometria lato client.
    """

    glass: GlassType
    capacity_ml: float | None
    compatible_ice: list[ServingIce]

    @classmethod
    def from_entity(cls, spec: GlassSpec) -> GlassOut:
        return cls(
            glass=spec.glass,
            capacity_ml=spec.capacity_ml,
            compatible_ice=list(spec.compatible_ice),
        )
