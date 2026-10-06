"""DTO dell'ottimizzazione."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.application.solver.models import (
    SolverResult,
    SolverSettings,
    SolverStatus,
    TargetProfile,
    TargetResidual,
    TargetWeights,
    VolumeBounds,
)

from .recipes import BalanceProfileOut, RecipeIn, RecipeOut


class TargetProfileIn(BaseModel):
    """I target richiesti, misurati sul drink **dopo** la diluizione."""

    model_config = ConfigDict(extra="forbid")

    abv: Annotated[float | None, Field(ge=0.0, le=1.0)] = Field(
        default=None, description="ABV finale come frazione (0.16 = 16% vol)"
    )
    brix: Annotated[float | None, Field(ge=0.0, le=100.0)] = Field(
        default=None, description="Gradi Brix finali"
    )
    acidity: Annotated[float | None, Field(ge=0.0, le=10.0)] = Field(
        default=None, description="Acidità finale in % peso/volume"
    )
    sugar_acid_ratio: Annotated[float | None, Field(gt=0.0, le=100.0)] = Field(
        default=None, description="Rapporto Brix/Acidità (sour equilibrato: 5.5-7.0)"
    )
    final_volume_ml: Annotated[float | None, Field(gt=0.0, le=1000.0)] = Field(
        default=None,
        description="Volume del drink servito. Trattato come vincolo rigido, non come obiettivo.",
    )

    @model_validator(mode="after")
    def at_least_one_target(self) -> TargetProfileIn:
        if all(
            value is None
            for value in (
                self.abv,
                self.brix,
                self.acidity,
                self.sugar_acid_ratio,
                self.final_volume_ml,
            )
        ):
            raise ValueError("specify at least one target")
        return self

    def to_domain(self) -> TargetProfile:
        return TargetProfile(
            abv=self.abv,
            brix=self.brix,
            acidity=self.acidity,
            sugar_acid_ratio=self.sugar_acid_ratio,
            final_volume_ml=self.final_volume_ml,
        )


class VolumeBoundsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_ml: Annotated[float, Field(gt=0.0, le=1000.0)] = 5.0
    max_ml: Annotated[float, Field(gt=0.0, le=1000.0)] = 120.0


class TargetWeightsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    abv: Annotated[float, Field(ge=0.0, le=100.0)] = 1.0
    brix: Annotated[float, Field(ge=0.0, le=100.0)] = 1.0
    acidity: Annotated[float, Field(ge=0.0, le=100.0)] = 1.0
    sugar_acid_ratio: Annotated[float, Field(ge=0.0, le=100.0)] = 1.0


class SolverSettingsIn(BaseModel):
    """Configurazione opzionale della minimizzazione.

    Esposta perché i bounds per ingrediente sono una leva reale di
    composizione: "il gin non scende sotto i 45 ml" è una scelta d'autore,
    non un dettaglio numerico, e senza questo campo l'unico modo di
    ottenerla sarebbe rifiutare a mano i risultati del solver.
    """

    model_config = ConfigDict(extra="forbid")

    default_bounds: VolumeBoundsIn = VolumeBoundsIn()
    bounds_by_ingredient: dict[str, VolumeBoundsIn] = {}
    weights: TargetWeightsIn = TargetWeightsIn()
    rounding_step_ml: Annotated[float, Field(gt=0.0, le=10.0)] = 0.5
    restarts: Annotated[int, Field(ge=0, le=32)] = 4

    def to_domain(self) -> SolverSettings:
        return SolverSettings(
            default_bounds=VolumeBounds(
                min_ml=self.default_bounds.min_ml, max_ml=self.default_bounds.max_ml
            ),
            bounds_by_ingredient={
                ingredient_id: VolumeBounds(min_ml=bounds.min_ml, max_ml=bounds.max_ml)
                for ingredient_id, bounds in self.bounds_by_ingredient.items()
            },
            weights=TargetWeights(
                abv=self.weights.abv,
                brix=self.weights.brix,
                acidity=self.weights.acidity,
                sugar_acid_ratio=self.weights.sugar_acid_ratio,
            ),
            rounding_step_ml=self.rounding_step_ml,
            restarts=self.restarts,
        )


class OptimizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe: RecipeIn
    target: TargetProfileIn
    settings: SolverSettingsIn | None = None


class OptimizeStoredRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: TargetProfileIn
    settings: SolverSettingsIn | None = None


class TargetResidualOut(BaseModel):
    name: str
    target: float
    achieved: float | None
    absolute_error: float | None
    relative_error: float | None

    @classmethod
    def from_entity(cls, residual: TargetResidual) -> TargetResidualOut:
        return cls(
            name=residual.name,
            target=residual.target,
            achieved=residual.achieved,
            absolute_error=residual.absolute_error,
            relative_error=residual.relative_error,
        )


class SolverResultOut(BaseModel):
    """Esito dell'ottimizzazione, diagnostica inclusa.

    `status` e `residuals` non sono decorazioni: senza di essi una ricetta
    prodotta da un solver che non è convergiuto è indistinguibile da una
    ottimizzata bene, e il client non ha modo di avvertire l'utente.
    """

    status: SolverStatus
    recipe: RecipeOut
    profile: BalanceProfileOut
    objective_value: float
    iterations: int
    residuals: list[TargetResidualOut]
    max_relative_error: float | None
    message: str

    @classmethod
    def from_entity(cls, result: SolverResult) -> SolverResultOut:
        return cls(
            status=result.status,
            recipe=RecipeOut.from_entity(result.recipe),
            profile=BalanceProfileOut.from_entity(result.profile, result.recipe.family),
            objective_value=result.objective_value,
            iterations=result.iterations,
            residuals=[TargetResidualOut.from_entity(item) for item in result.residuals],
            max_relative_error=result.max_relative_error,
            message=result.message,
        )
