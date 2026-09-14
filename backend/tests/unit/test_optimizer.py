import pytest

from app.domain.calculator import calculate_recipe_profile
from app.domain.models import (
    DilutionMethod,
    Ingredient,
    PhysicalProfile,
    Recipe,
    RecipeIngredient,
)
from app.domain.optimizer import TargetProfile, optimize_recipe_volumes


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


def make_unbalanced_daiquiri() -> Recipe:
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

    return Recipe(
        id="unbalanced-daiquiri",
        nome="Unbalanced Daiquiri",
        ingredienti=[
            RecipeIngredient(ingrediente=rum, volume_ml=50.0),
            RecipeIngredient(ingrediente=lime, volume_ml=15.0),
            RecipeIngredient(ingrediente=simple_syrup, volume_ml=35.0),
        ],
        dilution_method=DilutionMethod.SHAKEN,
    )


def test_optimizer_improves_unbalanced_daiquiri_towards_target() -> None:
    recipe = make_unbalanced_daiquiri()
    initial_profile = calculate_recipe_profile(recipe)

    target = TargetProfile(
        target_abv=0.16,
        target_brix=10.0,
        target_acidity=1.0,
    )

    optimized_recipe = optimize_recipe_volumes(recipe, target)
    optimized_profile = calculate_recipe_profile(optimized_recipe)

    assert abs(optimized_profile.abv_post - 0.16) < abs(initial_profile.abv_post - 0.16)
    assert abs(optimized_profile.brix_post - 10.0) < abs(initial_profile.brix_post - 10.0)
    assert abs(optimized_profile.acidity_post - 1.0) < abs(initial_profile.acidity_post - 1.0)

    assert optimized_profile.abv_post == pytest.approx(0.16, abs=0.03)
    assert optimized_profile.brix_post == pytest.approx(10.0, abs=1.5)
    assert optimized_profile.acidity_post == pytest.approx(1.0, abs=0.35)


def test_optimizer_respects_volume_bounds() -> None:
    recipe = make_unbalanced_daiquiri()
    target = TargetProfile(
        target_abv=0.30,
        target_brix=4.0,
        target_acidity=2.0,
        target_volume_ml=85.0,
    )

    optimized_recipe = optimize_recipe_volumes(
        recipe,
        target,
        min_volume=10.0,
        max_volume=40.0,
    )

    optimized_volumes = [ingredient.volume_ml for ingredient in optimized_recipe.ingredienti]

    assert all(10.0 <= volume <= 40.0 for volume in optimized_volumes)
    assert optimized_volumes == [round(volume, 1) for volume in optimized_volumes]
