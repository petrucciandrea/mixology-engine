"""Le entità non possono esistere in uno stato illegale."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.domain.entities import (
    Ingredient,
    PhysicalProfile,
    Recipe,
    RecipeIngredient,
)
from app.domain.enums import DilutionMethod, IngredientCategory, RecipeFamily, ServingIce
from app.domain.errors import (
    InvalidPhysicalProfileError,
    InvalidRecipeError,
    InvalidVolumeError,
)


class TestPhysicalProfile:
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("abv", -0.01),
            ("abv", 1.01),
            ("brix", -1.0),
            ("brix", 100.1),
            ("acidity", -0.1),
            # Il domain model definisce l'acidità in [0, 10]: una soluzione
            # più concentrata è fuori dal modello e va diluita prima.
            ("acidity", 10.1),
            # Nessun liquido da bar pesa 5 g/ml: prima il vincolo era
            # `le=100`, e un refuso di questo tipo passava indisturbato
            # fino a produrre un profilo assurdo.
            ("density_g_ml", 5.0),
            ("density_g_ml", 0.5),
        ],
    )
    def test_rejects_values_outside_the_physical_range(self, field: str, value: float) -> None:
        valid = {"density_g_ml": 1.0, "brix": 10.0, "acidity": 1.0, "abv": 0.2}
        valid[field] = value
        with pytest.raises(InvalidPhysicalProfileError):
            PhysicalProfile(**valid)  # type: ignore[arg-type]

    def test_rejects_nan(self) -> None:
        with pytest.raises(InvalidPhysicalProfileError):
            PhysicalProfile(density_g_ml=float("nan"), brix=0.0, acidity=0.0, abv=0.0)

    def test_accepts_the_extremes_of_the_range(self) -> None:
        PhysicalProfile(density_g_ml=0.70, brix=0.0, acidity=0.0, abv=0.0)
        PhysicalProfile(density_g_ml=1.60, brix=100.0, acidity=10.0, abv=1.0)


class TestRecipeIngredient:
    @pytest.mark.parametrize("volume", [0.0, -10.0])
    def test_rejects_non_positive_volume(self, white_rum: Ingredient, volume: float) -> None:
        with pytest.raises(InvalidVolumeError):
            RecipeIngredient(ingredient=white_rum, volume_ml=volume)

    def test_with_volume_returns_a_new_dose(self, white_rum: Ingredient) -> None:
        original = RecipeIngredient(ingredient=white_rum, volume_ml=45.0)
        updated = original.with_volume(60.0)

        assert updated.volume_ml == 60.0
        assert original.volume_ml == 45.0, "le entità sono immutabili"
        assert updated.ingredient is original.ingredient


class TestRecipe:
    def test_rejects_an_empty_recipe(self) -> None:
        with pytest.raises(InvalidRecipeError):
            Recipe(
                id="empty",
                name="Empty",
                dilution_method=DilutionMethod.SHAKEN,
                serving_ice=ServingIce.NONE,
                ingredients=(),
            )

    def test_rejects_the_same_ingredient_twice(self, white_rum: Ingredient) -> None:
        """Due dosi dello stesso ingrediente renderebbero ambiguo il solver.

        Il solver assegna un volume per posizione: con l'ingrediente
        ripetuto, due posizioni diverse descriverebbero lo stesso liquido e
        la soluzione non sarebbe più unica.
        """
        with pytest.raises(InvalidRecipeError, match="more than once"):
            Recipe(
                id="duplicate",
                name="Duplicate",
                dilution_method=DilutionMethod.SHAKEN,
                serving_ice=ServingIce.NONE,
                ingredients=(
                    RecipeIngredient(ingredient=white_rum, volume_ml=30.0),
                    RecipeIngredient(ingredient=white_rum, volume_ml=15.0),
                ),
            )

    def test_volumes_preserve_the_ingredient_order(self, daiquiri: Recipe) -> None:
        assert daiquiri.volumes_ml == (60.0, 30.0, 20.0)

    def test_with_volumes_replaces_the_dosage_in_place(self, daiquiri: Recipe) -> None:
        rebalanced = daiquiri.with_volumes((50.0, 25.0, 18.0))

        assert rebalanced.volumes_ml == (50.0, 25.0, 18.0)
        assert daiquiri.volumes_ml == (60.0, 30.0, 20.0), "l'originale non cambia"
        assert [item.ingredient.id for item in rebalanced.ingredients] == [
            item.ingredient.id for item in daiquiri.ingredients
        ]

    def test_with_volumes_rejects_a_vector_of_the_wrong_length(self, daiquiri: Recipe) -> None:
        """Il vettore del solver deve corrispondere agli ingredienti.

        Senza `strict=True` una lunghezza sbagliata produrrebbe una ricetta
        troncata in silenzio: il bug peggiore possibile, perché il
        risultato resta plausibile.
        """
        with pytest.raises(ValueError, match="argument"):
            daiquiri.with_volumes((50.0, 25.0))

    def test_rejects_blank_identity(self, white_rum: Ingredient) -> None:
        with pytest.raises(InvalidRecipeError):
            Recipe(
                id="   ",
                name="No Id",
                dilution_method=DilutionMethod.SHAKEN,
                serving_ice=ServingIce.NONE,
                ingredients=(RecipeIngredient(ingredient=white_rum, volume_ml=30.0),),
            )


class TestRecipeFamily:
    def test_the_family_is_optional(self, daiquiri: Recipe) -> None:
        assert daiquiri.family is None

    def test_a_recipe_carries_its_family(self, daiquiri: Recipe) -> None:
        assert replace(daiquiri, family=RecipeFamily.SOUR).family is RecipeFamily.SOUR

    def test_with_volumes_preserves_the_family(self, daiquiri: Recipe) -> None:
        sour = replace(daiquiri, family=RecipeFamily.SOUR)
        assert sour.with_volumes([50.0, 25.0, 15.0]).family is RecipeFamily.SOUR


class TestIngredient:
    def test_rejects_blank_name(self) -> None:
        with pytest.raises(InvalidRecipeError):
            Ingredient(
                id="x",
                name="",
                category=IngredientCategory.SPIRIT,
                physical_profile=PhysicalProfile(density_g_ml=0.95, brix=0.0, acidity=0.0, abv=0.4),
            )

    def test_is_active_by_default(self, white_rum: Ingredient) -> None:
        assert white_rum.is_active is True
