from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DilutionMethod(str, Enum):
    SHAKEN = "SHAKEN"
    STIRRED = "STIRRED"
    BUILD = "BUILD"


class PhysicalProfile(BaseModel):
    density_g_ml: float = Field(..., ge=0.0, le=100.0)
    brix: float = Field(..., ge=0.0, le=100.0)
    acidity: float = Field(..., ge=0.0, le=100.0)
    abv: float = Field(..., ge=0.0, le=1.0)


class Ingredient(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nome: str
    categoria: str
    physical_profile: PhysicalProfile


class RecipeIngredient(BaseModel):
    ingrediente: Ingredient
    volume_ml: float

    @field_validator("volume_ml")
    @classmethod
    def validate_volume_ml(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("volume_ml must be greater than 0")
        return value


class Recipe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nome: str
    ingredienti: list[RecipeIngredient]
    dilution_method: DilutionMethod


class CalculatedProfile(BaseModel):
    volume_total_ml: float
    pure_alcohol_ml: float
    abv_pre: float
    mass_total_g: float
    sugar_mass_g: float
    brix_pre: float
    acid_mass_g: float
    acidity_pre: float
    sugar_to_acid_ratio: float | None = None
    dilution_factor: float
    dilution_water_ml: float
    final_volume_ml: float
    abv_post: float
    brix_post: float
    acidity_post: float
