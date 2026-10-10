"""DTO delle ricette e del profilo di bilanciamento."""

from __future__ import annotations

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

from app.application.use_cases.balancing import BalanceResult
from app.domain.balance import (
    SOUR_RATIO_LOWER_BOUND,
    SOUR_RATIO_UPPER_BOUND,
    BalanceProfile,
    ServingProfile,
    SourBalance,
    assess_sour_balance,
)
from app.domain.entities import Recipe
from app.domain.enums import DilutionMethod, GlassType, RecipeFamily, ServingIce
from app.domain.services.glassware import GlassFit
from app.domain.services.serving_dilution import MAX_CONSUMPTION_MINUTES

from .ingredients import IngredientOut

#: Parametro di query condiviso dagli endpoint di bilanciamento.
ConsumptionMinutes = Annotated[
    float,
    Query(
        gt=0.0,
        le=MAX_CONSUMPTION_MINUTES,
        description="Minuti di contatto col ghiaccio di servizio (profilo `serving_profile`)",
    ),
]


class RecipeIngredientIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: str
    volume_ml: Annotated[float, Field(gt=0.0, le=1000.0)]


class RecipeIn(BaseModel):
    """Una ricetta così come arriva dall'editor, prima di essere salvata."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=255)]
    dilution_method: DilutionMethod
    serving_ice: ServingIce
    glass: GlassType | None = None
    family: RecipeFamily | None = None
    ingredients: Annotated[list[RecipeIngredientIn], Field(min_length=1, max_length=20)]
    instructions: str | None = None


class RecipeIngredientOut(BaseModel):
    ingredient: IngredientOut
    volume_ml: float


class RecipeOut(BaseModel):
    id: str
    name: str
    dilution_method: DilutionMethod
    serving_ice: ServingIce
    glass: GlassType | None = None
    family: RecipeFamily | None = None
    ingredients: list[RecipeIngredientOut]
    instructions: str | None = None

    @classmethod
    def from_entity(cls, entity: Recipe) -> RecipeOut:
        return cls(
            id=entity.id,
            name=entity.name,
            dilution_method=entity.dilution_method,
            serving_ice=entity.serving_ice,
            glass=entity.glass,
            family=entity.family,
            instructions=entity.instructions,
            ingredients=[
                RecipeIngredientOut(
                    ingredient=IngredientOut.from_entity(item.ingredient),
                    volume_ml=item.volume_ml,
                )
                for item in entity.ingredients
            ],
        )


class RecipePageOut(BaseModel):
    items: list[RecipeOut]
    total: int
    limit: int
    offset: int


class BalanceProfileOut(BaseModel):
    """Il profilo calcolato, con le grandezze intermedie.

    Le masse e il volume di alcol puro non servono a un'interfaccia
    grafica, ma rendono il risultato verificabile: chi dubita di un numero
    può rifare il conto invece di fidarsi.
    """

    total_volume_ml: float
    pure_alcohol_ml: float
    total_mass_g: float
    sugar_mass_g: float
    acid_mass_g: float

    abv_pre: float
    brix_pre: float
    acidity_pre: float
    sugar_acid_ratio: float | None

    dilution_factor: float
    dilution_water_ml: float
    final_volume_ml: float
    final_mass_g: float

    abv_post: float
    brix_post: float
    acidity_post: float

    abv_post_percent: float
    #: Giudizio dolce/equilibrato/aspro: solo per i sour con acidità
    #: percepibile, `null` altrove (vedi `assess_sour_balance`).
    sour_balance: SourBalance | None
    #: Estremi della finestra, perché l'interfaccia disegni la barra senza
    #: riscriverli: la soglia vive nel dominio e in un posto solo.
    sour_ratio_lower_bound: float = SOUR_RATIO_LOWER_BOUND
    sour_ratio_upper_bound: float = SOUR_RATIO_UPPER_BOUND

    @classmethod
    def from_entity(cls, profile: BalanceProfile, family: RecipeFamily | None) -> BalanceProfileOut:
        return cls(
            total_volume_ml=profile.total_volume_ml,
            pure_alcohol_ml=profile.pure_alcohol_ml,
            total_mass_g=profile.total_mass_g,
            sugar_mass_g=profile.sugar_mass_g,
            acid_mass_g=profile.acid_mass_g,
            abv_pre=profile.abv_pre,
            brix_pre=profile.brix_pre,
            acidity_pre=profile.acidity_pre,
            sugar_acid_ratio=profile.sugar_acid_ratio,
            dilution_factor=profile.dilution_factor,
            dilution_water_ml=profile.dilution_water_ml,
            final_volume_ml=profile.final_volume_ml,
            final_mass_g=profile.final_mass_g,
            abv_post=profile.abv_post,
            brix_post=profile.brix_post,
            acidity_post=profile.acidity_post,
            abv_post_percent=profile.abv_post_percent,
            sour_balance=assess_sour_balance(family, profile),
        )


class ServingProfileOut(BaseModel):
    """Il drink dopo la diluizione dovuta al ghiaccio di servizio."""

    consumption_minutes: float
    initial_temperature_c: float
    temperature_c: float
    freezing_point_c: float
    ambient_heat_j: float
    melt_water_ml: float
    ice_mass_g: float
    remaining_ice_g: float
    final_volume_ml: float
    final_mass_g: float
    total_dilution_factor: float
    abv: float
    abv_percent: float
    brix: float
    acidity: float

    @classmethod
    def from_entity(cls, profile: ServingProfile) -> ServingProfileOut:
        return cls(
            consumption_minutes=profile.consumption_minutes,
            initial_temperature_c=profile.initial_temperature_c,
            temperature_c=profile.temperature_c,
            freezing_point_c=profile.freezing_point_c,
            ambient_heat_j=profile.ambient_heat_j,
            melt_water_ml=profile.melt_water_ml,
            ice_mass_g=profile.ice_mass_g,
            remaining_ice_g=profile.remaining_ice_g,
            final_volume_ml=profile.final_volume_ml,
            final_mass_g=profile.final_mass_g,
            total_dilution_factor=profile.total_dilution_factor,
            abv=profile.abv,
            abv_percent=profile.abv_percent,
            brix=profile.brix,
            acidity=profile.acidity,
        )


class GlassFitOut(BaseModel):
    """Quanto il drink riempie il suo bicchiere; `fill_ratio` > 1 = trabocca."""

    capacity_ml: float
    max_volume_ml: float
    ice_volume_ml: float
    volume_ml: float
    fill_ratio: float
    overflows: bool

    @classmethod
    def from_entity(cls, fit: GlassFit) -> GlassFitOut:
        return cls(
            capacity_ml=fit.capacity_ml,
            max_volume_ml=fit.max_volume_ml,
            ice_volume_ml=fit.ice_volume_ml,
            volume_ml=fit.volume_ml,
            fill_ratio=fit.fill_ratio,
            overflows=fit.overflows,
        )


class BalanceOut(BaseModel):
    """Risposta del calcolo: la ricetta risolta e i suoi profili.

    `serving_profile` e `serving_curve` sono `null` per le ricette servite
    senza ghiaccio, `glass_fit` per quelle senza bicchiere (o con bicchiere
    senza capienza). `serving_curve` è lo stesso profilo di servizio
    campionato al minuto dal momento del servizio (`t = 0`) a 30 minuti.
    """

    recipe: RecipeOut
    profile: BalanceProfileOut
    serving_profile: ServingProfileOut | None = None
    serving_curve: list[ServingProfileOut] | None = None
    glass_fit: GlassFitOut | None = None

    @classmethod
    def from_result(cls, result: BalanceResult) -> BalanceOut:
        return cls(
            recipe=RecipeOut.from_entity(result.recipe),
            profile=BalanceProfileOut.from_entity(result.profile, result.recipe.family),
            serving_profile=(
                ServingProfileOut.from_entity(result.serving)
                if result.serving is not None
                else None
            ),
            serving_curve=(
                [ServingProfileOut.from_entity(point) for point in result.serving_curve]
                if result.serving_curve is not None
                else None
            ),
            glass_fit=(
                GlassFitOut.from_entity(result.glass_fit) if result.glass_fit is not None else None
            ),
        )
