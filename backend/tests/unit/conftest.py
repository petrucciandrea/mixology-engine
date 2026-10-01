"""Ingredienti di riferimento per i test di dominio.

Sono valori realistici e verificabili, non numeri di comodo: il rum a
40% vol e densità 0.95, il lime a 6% di acido citrico e 7.5 °Bx, lo
sciroppo 1:1 a 50 °Bx. Usare dati veri significa che un test che fallisce
segnala un errore nel modello, non nella fixture.
"""

from __future__ import annotations

import pytest

from app.domain.entities import Ingredient, PhysicalProfile, Recipe, RecipeIngredient
from app.domain.enums import DilutionMethod, IngredientCategory, ServingIce
from app.domain.flavor import FlavorProfile


def make_ingredient(
    ingredient_id: str,
    name: str,
    category: IngredientCategory,
    *,
    abv: float,
    brix: float,
    acidity: float,
    density_g_ml: float,
    flavor: FlavorProfile | None = None,
) -> Ingredient:
    return Ingredient(
        id=ingredient_id,
        name=name,
        category=category,
        physical_profile=PhysicalProfile(
            density_g_ml=density_g_ml, brix=brix, acidity=acidity, abv=abv
        ),
        flavor_profile=flavor,
    )


@pytest.fixture
def white_rum() -> Ingredient:
    return make_ingredient(
        "rum",
        "Rum Bianco",
        IngredientCategory.SPIRIT,
        abv=0.40,
        brix=0.0,
        acidity=0.0,
        density_g_ml=0.95,
        flavor=FlavorProfile.from_descriptors(
            alcohol_heat=0.6, tropical_fruit=0.3, funky=0.25, vanilla=0.15
        ),
    )


@pytest.fixture
def lime_juice() -> Ingredient:
    return make_ingredient(
        "lime",
        "Succo di Lime",
        IngredientCategory.JUICE,
        abv=0.0,
        brix=7.5,
        acidity=6.0,
        density_g_ml=1.03,
        flavor=FlavorProfile.from_descriptors(sour=0.95, citrus=0.9, herbaceous=0.2),
    )


@pytest.fixture
def simple_syrup() -> Ingredient:
    return make_ingredient(
        "simple-syrup",
        "Sciroppo Semplice 1:1",
        IngredientCategory.SYRUP,
        abv=0.0,
        brix=50.0,
        acidity=0.0,
        density_g_ml=1.23,
        flavor=FlavorProfile.from_descriptors(sweet=1.0),
    )


@pytest.fixture
def gin() -> Ingredient:
    return make_ingredient(
        "gin",
        "London Dry Gin",
        IngredientCategory.SPIRIT,
        abv=0.43,
        brix=0.0,
        acidity=0.0,
        density_g_ml=0.94,
        flavor=FlavorProfile.from_descriptors(
            alcohol_heat=0.65, resinous=0.8, citrus=0.4, pepper=0.3, herbaceous=0.35
        ),
    )


@pytest.fixture
def sweet_vermouth() -> Ingredient:
    return make_ingredient(
        "sweet-vermouth",
        "Vermouth Rosso",
        IngredientCategory.FORTIFIED_WINE,
        abv=0.16,
        brix=16.0,
        acidity=0.5,
        density_g_ml=1.05,
        flavor=FlavorProfile.from_descriptors(
            sweet=0.6, bitter=0.3, dried_fruit=0.5, warm_spice=0.4, herbaceous=0.3
        ),
    )


@pytest.fixture
def campari() -> Ingredient:
    return make_ingredient(
        "campari",
        "Bitter Rosso",
        IngredientCategory.BITTER,
        abv=0.25,
        brix=24.0,
        acidity=0.4,
        density_g_ml=1.06,
        flavor=FlavorProfile.from_descriptors(
            bitter=0.95, sweet=0.5, citrus=0.5, medicinal=0.4, floral=0.2
        ),
    )


@pytest.fixture
def daiquiri(white_rum: Ingredient, lime_juice: Ingredient, simple_syrup: Ingredient) -> Recipe:
    """Daiquiri classico 60/30/20 — il riferimento di ogni sour."""
    return Recipe(
        id="classic-daiquiri",
        name="Classic Daiquiri",
        dilution_method=DilutionMethod.SHAKEN,
        serving_ice=ServingIce.NONE,
        ingredients=(
            RecipeIngredient(ingredient=white_rum, volume_ml=60.0),
            RecipeIngredient(ingredient=lime_juice, volume_ml=30.0),
            RecipeIngredient(ingredient=simple_syrup, volume_ml=20.0),
        ),
    )


@pytest.fixture
def negroni(gin: Ingredient, sweet_vermouth: Ingredient, campari: Ingredient) -> Recipe:
    """Negroni 30/30/30, mescolato."""
    return Recipe(
        id="negroni",
        name="Negroni",
        dilution_method=DilutionMethod.STIRRED,
        serving_ice=ServingIce.LARGE_CUBE,
        ingredients=(
            RecipeIngredient(ingredient=gin, volume_ml=30.0),
            RecipeIngredient(ingredient=sweet_vermouth, volume_ml=30.0),
            RecipeIngredient(ingredient=campari, volume_ml=30.0),
        ),
    )


@pytest.fixture
def unbalanced_daiquiri(
    white_rum: Ingredient, lime_juice: Ingredient, simple_syrup: Ingredient
) -> Recipe:
    """Stessi ingredienti, dosaggio sbilanciato: poco acido, troppo zucchero."""
    return Recipe(
        id="unbalanced-daiquiri",
        name="Unbalanced Daiquiri",
        dilution_method=DilutionMethod.SHAKEN,
        serving_ice=ServingIce.NONE,
        ingredients=(
            RecipeIngredient(ingredient=white_rum, volume_ml=50.0),
            RecipeIngredient(ingredient=lime_juice, volume_ml=15.0),
            RecipeIngredient(ingredient=simple_syrup, volume_ml=35.0),
        ),
    )
