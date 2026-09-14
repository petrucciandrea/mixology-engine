import pytest
from pydantic import ValidationError

from app.domain.calculator import calculate_recipe_profile
from app.domain.models import (
    DilutionMethod,
    Ingredient,
    PhysicalProfile,
    Recipe,
    RecipeIngredient,
)


def make_ingredient(
    ingredient_id: str,
    nome: str,
    categoria: str,
    *,
    abv: float,
    brix: float,
    acidity: float,
    density_g_ml: float,
) -> Ingredient:
    return Ingredient(
        id=ingredient_id,
        nome=nome,
        categoria=categoria,
        physical_profile=PhysicalProfile(
            density_g_ml=density_g_ml,
            brix=brix,
            acidity=acidity,
            abv=abv,
        ),
    )


def test_classic_daiquiri_profile() -> None:
    rum = make_ingredient(
        "rum",
        "Rum",
        "spirit",
        abv=0.40,
        brix=0.0,
        acidity=0.0,
        density_g_ml=0.95,
    )
    lime = make_ingredient(
        "lime",
        "Succo di Lime",
        "juice",
        abv=0.0,
        brix=7.5,
        acidity=6.0,
        density_g_ml=1.03,
    )
    simple_syrup = make_ingredient(
        "simple-syrup",
        "Sciroppo Semplice 1:1",
        "syrup",
        abv=0.0,
        brix=50.0,
        acidity=0.0,
        density_g_ml=1.23,
    )

    recipe = Recipe(
        id="classic-daiquiri",
        nome="Classic Daiquiri",
        ingredienti=[
            RecipeIngredient(ingrediente=rum, volume_ml=60.0),
            RecipeIngredient(ingrediente=lime, volume_ml=30.0),
            RecipeIngredient(ingrediente=simple_syrup, volume_ml=20.0),
        ],
        dilution_method=DilutionMethod.SHAKEN,
    )

    profile = calculate_recipe_profile(recipe)

    assert profile.volume_total_ml == pytest.approx(110.0)
    assert profile.abv_pre == pytest.approx(0.218, abs=1e-3)
    assert profile.dilution_water_ml > 0
    assert profile.abv_post < profile.abv_pre
    assert profile.brix_post < profile.brix_pre
    assert profile.sugar_to_acid_ratio is not None
    assert profile.sugar_to_acid_ratio > 0


def test_negroni_stirred_profile() -> None:
    gin = make_ingredient(
        "gin",
        "Gin",
        "spirit",
        abv=0.43,
        brix=0.0,
        acidity=0.0,
        density_g_ml=0.94,
    )
    sweet_vermouth = make_ingredient(
        "sweet-vermouth",
        "Sweet Vermouth",
        "fortified-wine",
        abv=0.16,
        brix=16.0,
        acidity=0.5,
        density_g_ml=1.05,
    )
    campari = make_ingredient(
        "campari",
        "Campari",
        "bitter",
        abv=0.25,
        brix=24.0,
        acidity=0.4,
        density_g_ml=1.06,
    )

    recipe = Recipe(
        id="negroni",
        nome="Negroni",
        ingredienti=[
            RecipeIngredient(ingrediente=gin, volume_ml=30.0),
            RecipeIngredient(ingrediente=sweet_vermouth, volume_ml=30.0),
            RecipeIngredient(ingrediente=campari, volume_ml=30.0),
        ],
        dilution_method=DilutionMethod.STIRRED,
    )

    profile = calculate_recipe_profile(recipe)

    assert profile.volume_total_ml == pytest.approx(90.0)
    assert profile.abv_pre == pytest.approx(0.280, abs=1e-3)
    assert profile.dilution_factor == pytest.approx(0.43784, abs=1e-5)
    assert profile.dilution_water_ml == pytest.approx(39.4056, abs=1e-4)
    assert profile.abv_post == pytest.approx(0.1947, abs=1e-3)
    assert profile.abv_post < profile.abv_pre


def test_sugar_to_acid_ratio_is_none_when_acidity_is_zero() -> None:
    whiskey = make_ingredient(
        "whiskey",
        "Whiskey",
        "spirit",
        abv=0.40,
        brix=0.0,
        acidity=0.0,
        density_g_ml=0.94,
    )
    syrup = make_ingredient(
        "syrup",
        "Syrup",
        "syrup",
        abv=0.0,
        brix=60.0,
        acidity=0.0,
        density_g_ml=1.20,
    )

    recipe = Recipe(
        id="zero-acidity",
        nome="Zero Acidity",
        ingredienti=[
            RecipeIngredient(ingrediente=whiskey, volume_ml=50.0),
            RecipeIngredient(ingrediente=syrup, volume_ml=10.0),
        ],
        dilution_method=DilutionMethod.SHAKEN,
    )

    profile = calculate_recipe_profile(recipe)

    assert profile.acidity_pre == pytest.approx(0.0)
    assert profile.sugar_to_acid_ratio is None


def test_build_method_has_no_ice_dilution() -> None:
    spirit = make_ingredient(
        "spirit",
        "Spirit",
        "spirit",
        abv=0.40,
        brix=0.0,
        acidity=0.0,
        density_g_ml=0.95,
    )
    mixer = make_ingredient(
        "mixer",
        "Mixer",
        "mixer",
        abv=0.0,
        brix=10.0,
        acidity=1.0,
        density_g_ml=1.00,
    )

    recipe = Recipe(
        id="build-drink",
        nome="Build Drink",
        ingredienti=[
            RecipeIngredient(ingrediente=spirit, volume_ml=50.0),
            RecipeIngredient(ingrediente=mixer, volume_ml=100.0),
        ],
        dilution_method=DilutionMethod.BUILD,
    )

    profile = calculate_recipe_profile(recipe)

    assert profile.dilution_factor == pytest.approx(0.0)
    assert profile.dilution_water_ml == pytest.approx(0.0)
    assert profile.abv_post == pytest.approx(profile.abv_pre)


def test_recipe_ingredient_raises_validation_error_for_non_positive_volume() -> None:
    ingredient = make_ingredient(
        "invalid-volume-ingredient",
        "Invalid Volume Ingredient",
        "test",
        abv=0.0,
        brix=0.0,
        acidity=0.0,
        density_g_ml=1.0,
    )

    with pytest.raises(ValidationError):
        RecipeIngredient(ingrediente=ingredient, volume_ml=0.0)

    with pytest.raises(ValidationError):
        RecipeIngredient(ingrediente=ingredient, volume_ml=-10.0)
