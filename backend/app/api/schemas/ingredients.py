"""DTO degli ingredienti."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities import (
    MAX_ACIDITY_PERCENT,
    MAX_BRIX,
    MAX_DENSITY_G_ML,
    MIN_DENSITY_G_ML,
    Ingredient,
)
from app.domain.enums import IngredientCategory
from app.domain.flavor import FLAVOR_DESCRIPTORS


class PhysicalProfileIn(BaseModel):
    """Le quattro grandezze misurabili di un ingrediente.

    I vincoli ripetono quelli del dominio: qui servono a produrre un 422
    con un messaggio utile e a documentarsi da soli in OpenAPI, mentre il
    dominio resta la sede della regola. La duplicazione è voluta e limitata
    ai soli range, che sono attinti dalle costanti del dominio invece di
    essere riscritti.
    """

    model_config = ConfigDict(extra="forbid")

    density_g_ml: Annotated[float, Field(ge=MIN_DENSITY_G_ML, le=MAX_DENSITY_G_ML)] = Field(
        ..., description="Densità in g/ml (alcol ~0.94, sciroppo 1:1 ~1.23, acqua 1.00)"
    )
    brix: Annotated[float, Field(ge=0.0, le=MAX_BRIX)] = Field(
        ..., description="Concentrazione zuccherina in gradi Brix (% in peso)"
    )
    acidity: Annotated[float, Field(ge=0.0, le=MAX_ACIDITY_PERCENT)] = Field(
        ..., description="Acido equivalente in % peso/volume"
    )
    abv: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        ..., description="Titolo alcolometrico come frazione, non percentuale (0.40 = 40% vol)"
    )


class PhysicalProfileOut(PhysicalProfileIn):
    pass


class IngredientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=255)]
    category: IngredientCategory
    physical_profile: PhysicalProfileIn
    flavor_profile: dict[str, Annotated[float, Field(ge=0.0, le=1.0)]] | None = Field(
        default=None,
        description=(
            "Profilo organolettico: mappa descrittore → intensità in [0, 1]. "
            "Vanno indicati solo i descrittori non nulli; i nomi ammessi sono "
            f"i {len(FLAVOR_DESCRIPTORS)} di GET /api/v1/ingredients/flavor-descriptors."
        ),
    )


class IngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: IngredientCategory
    physical_profile: PhysicalProfileOut
    flavor_profile: dict[str, float] | None = None
    #: Solo i descrittori più intensi, per le liste e le anteprime: l'intero
    #: vettore è rumore visivo quando servono venti ingredienti in pagina.
    dominant_flavors: list[str] = []
    is_active: bool

    @classmethod
    def from_entity(cls, entity: Ingredient) -> IngredientOut:
        return cls(
            id=entity.id,
            name=entity.name,
            category=entity.category,
            physical_profile=PhysicalProfileOut(
                density_g_ml=entity.physical_profile.density_g_ml,
                brix=entity.physical_profile.brix,
                acidity=entity.physical_profile.acidity,
                abv=entity.physical_profile.abv,
            ),
            flavor_profile=(
                entity.flavor_profile.as_dict() if entity.flavor_profile is not None else None
            ),
            dominant_flavors=(
                [name for name, _ in entity.flavor_profile.dominant()]
                if entity.flavor_profile is not None
                else []
            ),
            is_active=entity.is_active,
        )


class IngredientPageOut(BaseModel):
    items: list[IngredientOut]
    total: int
    limit: int
    offset: int


class FlavorDescriptorsOut(BaseModel):
    """Il vocabolario organolettico, esposto perché il client lo usi.

    Senza questo endpoint ogni consumatore dovrebbe conoscere a memoria i
    nomi dei descrittori, e un refuso si scoprirebbe solo a runtime.
    """

    dimension: int
    descriptors: list[str]
    families: dict[str, list[str]]
