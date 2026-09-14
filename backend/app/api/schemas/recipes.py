"""DTO delle ricette e del profilo di bilanciamento."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.domain.balance import BalanceProfile
from app.domain.entities import Recipe
from app.domain.enums import DilutionMethod

from .ingredients import IngredientOut


class RecipeIngredientIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: str
    volume_ml: Annotated[float, Field(gt=0.0, le=1000.0)]


class RecipeIn(BaseModel):
    """Una ricetta così come arriva dall'editor, prima di essere salvata."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=255)]
    dilution_method: DilutionMethod
    ingredients: Annotated[list[RecipeIngredientIn], Field(min_length=1, max_length=20)]
    instructions: str | None = None


class RecipeIngredientOut(BaseModel):
    ingredient: IngredientOut
    volume_ml: float


class RecipeOut(BaseModel):
    id: str
    name: str
    dilution_method: DilutionMethod
    ingredients: list[RecipeIngredientOut]
    instructions: str | None = None

    @classmethod
    def from_entity(cls, entity: Recipe) -> RecipeOut:
        return cls(
            id=entity.id,
            name=entity.name,
            dilution_method=entity.dilution_method,
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
    is_balanced_sour: bool

    @classmethod
    def from_entity(cls, profile: BalanceProfile) -> BalanceProfileOut:
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
            is_balanced_sour=profile.is_balanced_sour,
        )


class BalanceOut(BaseModel):
    """Risposta del calcolo: la ricetta risolta e il suo profilo."""

    recipe: RecipeOut
    profile: BalanceProfileOut
