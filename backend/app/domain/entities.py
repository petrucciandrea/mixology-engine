"""Entità e value object del dominio.

Sono `dataclass` frozen della sola libreria standard: **il dominio non
importa Pydantic, SQLAlchemy o SciPy**. È la regola di dipendenza di
Clean Architecture applicata letteralmente — il cuore del sistema non
conosce il framework web, l'ORM, né la libreria di ottimizzazione, e i
suoi test girano senza che nessuno di essi sia installato.

La validazione vive negli `__post_init__`: un'entità che esiste è
un'entità valida, e non c'è modo di costruirne una in stato illegale.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Final

from .enums import DilutionMethod, GlassType, IngredientCategory, RecipeFamily, ServingIce
from .errors import InvalidPhysicalProfileError, InvalidRecipeError, InvalidVolumeError
from .flavor import FlavorProfile

# ---------------------------------------------------------------------------
# Limiti fisici del dominio.
#
# Non sono limiti difensivi arbitrari: delimitano ciò per cui il modello di
# bilanciamento è stato scritto. Un liquido da bar sta fra l'alcol ad alta
# gradazione (~0.79 g/ml) e il miele puro (~1.42 g/ml); il margine porta il
# tetto a 1.60. L'acidità è espressa in % peso/volume di acido equivalente
# e il domain model la definisce nell'intervallo [0, 10]: le soluzioni acide
# più concentrate (super juice, acidi in polvere) sono fuori dal modello e
# vanno diluite prima di essere inserite come ingrediente.
# ---------------------------------------------------------------------------

MIN_DENSITY_G_ML: Final[float] = 0.70
MAX_DENSITY_G_ML: Final[float] = 1.60
MAX_BRIX: Final[float] = 100.0
MAX_ACIDITY_PERCENT: Final[float] = 10.0


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise InvalidPhysicalProfileError(f"{name} must be a finite number, got {value!r}")


@dataclass(frozen=True, slots=True)
class PhysicalProfile:
    """Le quattro grandezze misurabili da cui dipende tutto il bilanciamento.

    Sono le uniche proprietà di un ingrediente che il solver usa: il
    profilo organolettico serve al matcher, non alla matematica.
    """

    density_g_ml: float
    brix: float
    acidity: float
    abv: float

    def __post_init__(self) -> None:
        for name, value in (
            ("density_g_ml", self.density_g_ml),
            ("brix", self.brix),
            ("acidity", self.acidity),
            ("abv", self.abv),
        ):
            _require_finite(name, value)

        if not MIN_DENSITY_G_ML <= self.density_g_ml <= MAX_DENSITY_G_ML:
            raise InvalidPhysicalProfileError(
                f"density_g_ml must be within [{MIN_DENSITY_G_ML}, {MAX_DENSITY_G_ML}] g/ml, "
                f"got {self.density_g_ml}"
            )
        if not 0.0 <= self.brix <= MAX_BRIX:
            raise InvalidPhysicalProfileError(
                f"brix must be within [0.0, {MAX_BRIX}] °Bx, got {self.brix}"
            )
        if not 0.0 <= self.acidity <= MAX_ACIDITY_PERCENT:
            raise InvalidPhysicalProfileError(
                f"acidity must be within [0.0, {MAX_ACIDITY_PERCENT}] % w/v, got {self.acidity}"
            )
        if not 0.0 <= self.abv <= 1.0:
            raise InvalidPhysicalProfileError(
                f"abv must be a fraction within [0.0, 1.0], got {self.abv}"
            )


@dataclass(frozen=True, slots=True)
class Ingredient:
    """Un ingrediente del bar, con il suo profilo fisico e organolettico."""

    id: str
    name: str
    category: IngredientCategory
    physical_profile: PhysicalProfile
    flavor_profile: FlavorProfile | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidRecipeError("ingredient id must not be empty")
        if not self.name.strip():
            raise InvalidRecipeError("ingredient name must not be empty")


@dataclass(frozen=True, slots=True)
class RecipeIngredient:
    """Un ingrediente dosato: l'associazione fra un ingrediente e un volume."""

    ingredient: Ingredient
    volume_ml: float

    def __post_init__(self) -> None:
        _require_finite("volume_ml", self.volume_ml)
        if self.volume_ml <= 0:
            raise InvalidVolumeError(f"volume_ml must be greater than 0, got {self.volume_ml}")

    def with_volume(self, volume_ml: float) -> RecipeIngredient:
        return replace(self, volume_ml=volume_ml)


@dataclass(frozen=True, slots=True)
class Recipe:
    """Aggregate root: una ricetta è la lista dosata più tecnica e servizio.

    `dilution_method` descrive come si prepara, `serving_ice` come si serve:
    sono indipendenti (vedi `ServingIce`). `glass` è il bicchiere di
    servizio, facoltativo: se presente, fissa un tetto al volume del drink
    (vedi `domain/services/glassware`). `family` classifica il drink
    (vedi `RecipeFamily`) ed è facoltativa: non entra in nessun calcolo
    fisico, solo nel giudizio sul rapporto zuccheri/acidi, che vale per i
    sour (`assess_sour_balance`).

    L'invariante che protegge è la coerenza del dosaggio — nessuna ricetta
    vuota, nessun ingrediente ripetuto (due dosi dello stesso ingrediente
    sono una sola dose sommata, e tenerle separate renderebbe ambiguo il
    risultato del solver, che assegna un volume per posizione).
    """

    id: str
    name: str
    dilution_method: DilutionMethod
    serving_ice: ServingIce
    ingredients: tuple[RecipeIngredient, ...]
    instructions: str | None = None
    glass: GlassType | None = None
    family: RecipeFamily | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidRecipeError("recipe id must not be empty")
        if not self.name.strip():
            raise InvalidRecipeError("recipe name must not be empty")
        if not self.ingredients:
            raise InvalidRecipeError("a recipe must contain at least one ingredient")

        seen: set[str] = set()
        for item in self.ingredients:
            if item.ingredient.id in seen:
                raise InvalidRecipeError(
                    f"ingredient '{item.ingredient.id}' appears more than once; "
                    "merge the doses into a single entry"
                )
            seen.add(item.ingredient.id)

    @property
    def volumes_ml(self) -> tuple[float, ...]:
        """I volumi nell'ordine degli ingredienti: il vettore x del solver."""
        return tuple(item.volume_ml for item in self.ingredients)

    def with_volumes(self, volumes_ml: tuple[float, ...] | list[float]) -> Recipe:
        """Ricetta identica con nuovi volumi, posizione per posizione.

        È il ponte fra il vettore numerico del solver e il modello di
        dominio: il solver ragiona su un array di float, il dominio solo su
        ricette valide. `strict=True` impedisce che un vettore di lunghezza
        sbagliata produca silenziosamente una ricetta troncata.
        """
        return replace(
            self,
            ingredients=tuple(
                item.with_volume(volume)
                for item, volume in zip(self.ingredients, volumes_ml, strict=True)
            ),
        )
