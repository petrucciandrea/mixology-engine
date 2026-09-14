from __future__ import annotations

from .models import CalculatedProfile, DilutionMethod, Recipe, RecipeIngredient

WATER_DENSITY_G_ML = 1.0


def calculate_shaken_dilution_factor(abv_in: float) -> float:
    return (-1.567 * (abv_in**2)) + (1.742 * abv_in) + 0.203


def calculate_stirred_dilution_factor(abv_in: float) -> float:
    return (-1.150 * (abv_in**2)) + (1.350 * abv_in) + 0.150


def calculate_dilution_factor(method: DilutionMethod, abv_in: float) -> float:
    if method == DilutionMethod.SHAKEN:
        return calculate_shaken_dilution_factor(abv_in)
    if method == DilutionMethod.STIRRED:
        return calculate_stirred_dilution_factor(abv_in)
    return 0.0


def calculate_total_volume_ml(recipe_ingredients: list[RecipeIngredient]) -> float:
    return sum(item.volume_ml for item in recipe_ingredients)


def calculate_pure_alcohol_ml(recipe_ingredients: list[RecipeIngredient]) -> float:
    return sum(
        item.volume_ml * item.ingrediente.physical_profile.abv
        for item in recipe_ingredients
    )


def calculate_total_mass_g(recipe_ingredients: list[RecipeIngredient]) -> float:
    return sum(
        item.volume_ml * item.ingrediente.physical_profile.density_g_ml
        for item in recipe_ingredients
    )


def calculate_sugar_mass_g(recipe_ingredients: list[RecipeIngredient]) -> float:
    return sum(
        item.volume_ml
        * item.ingrediente.physical_profile.density_g_ml
        * (item.ingrediente.physical_profile.brix / 100.0)
        for item in recipe_ingredients
    )


def calculate_acid_mass_g(recipe_ingredients: list[RecipeIngredient]) -> float:
    return sum(
        item.volume_ml
        * item.ingrediente.physical_profile.density_g_ml
        * (item.ingrediente.physical_profile.acidity / 100.0)
        for item in recipe_ingredients
    )


def calculate_abv_pre(volume_total_ml: float, pure_alcohol_ml: float) -> float:
    if volume_total_ml == 0:
        return 0.0
    return pure_alcohol_ml / volume_total_ml


def calculate_brix_pre(mass_total_g: float, sugar_mass_g: float) -> float:
    if mass_total_g == 0:
        return 0.0
    return (sugar_mass_g / mass_total_g) * 100.0


def calculate_acidity_pre(mass_total_g: float, acid_mass_g: float) -> float:
    if mass_total_g == 0:
        return 0.0
    return (acid_mass_g / mass_total_g) * 100.0


def calculate_sugar_to_acid_ratio(
    brix_pre: float, acidity_pre: float
) -> float | None:
    if acidity_pre == 0:
        return None
    return brix_pre / acidity_pre


def calculate_dilution_water_ml(volume_total_ml: float, dilution_factor: float) -> float:
    return volume_total_ml * dilution_factor


def calculate_final_volume_ml(volume_total_ml: float, dilution_water_ml: float) -> float:
    return volume_total_ml + dilution_water_ml


def calculate_final_mass_g(mass_total_g: float, dilution_water_ml: float) -> float:
    return mass_total_g + (dilution_water_ml * WATER_DENSITY_G_ML)


def calculate_abv_post(final_volume_ml: float, pure_alcohol_ml: float) -> float:
    if final_volume_ml == 0:
        return 0.0
    return pure_alcohol_ml / final_volume_ml


def calculate_brix_post(final_mass_g: float, sugar_mass_g: float) -> float:
    if final_mass_g == 0:
        return 0.0
    return (sugar_mass_g / final_mass_g) * 100.0


def calculate_acidity_post(final_mass_g: float, acid_mass_g: float) -> float:
    if final_mass_g == 0:
        return 0.0
    return (acid_mass_g / final_mass_g) * 100.0


def calculate_recipe_profile(recipe: Recipe) -> CalculatedProfile:
    volume_total_ml = calculate_total_volume_ml(recipe.ingredienti)
    pure_alcohol_ml = calculate_pure_alcohol_ml(recipe.ingredienti)
    mass_total_g = calculate_total_mass_g(recipe.ingredienti)
    sugar_mass_g = calculate_sugar_mass_g(recipe.ingredienti)
    acid_mass_g = calculate_acid_mass_g(recipe.ingredienti)

    abv_pre = calculate_abv_pre(volume_total_ml, pure_alcohol_ml)
    brix_pre = calculate_brix_pre(mass_total_g, sugar_mass_g)
    acidity_pre = calculate_acidity_pre(mass_total_g, acid_mass_g)
    sugar_to_acid_ratio = calculate_sugar_to_acid_ratio(brix_pre, acidity_pre)

    dilution_factor = calculate_dilution_factor(recipe.dilution_method, abv_pre)
    dilution_water_ml = calculate_dilution_water_ml(volume_total_ml, dilution_factor)
    final_volume_ml = calculate_final_volume_ml(volume_total_ml, dilution_water_ml)
    final_mass_g = calculate_final_mass_g(mass_total_g, dilution_water_ml)

    abv_post = calculate_abv_post(final_volume_ml, pure_alcohol_ml)
    brix_post = calculate_brix_post(final_mass_g, sugar_mass_g)
    acidity_post = calculate_acidity_post(final_mass_g, acid_mass_g)

    return CalculatedProfile(
        volume_total_ml=volume_total_ml,
        pure_alcohol_ml=pure_alcohol_ml,
        abv_pre=abv_pre,
        mass_total_g=mass_total_g,
        sugar_mass_g=sugar_mass_g,
        brix_pre=brix_pre,
        acid_mass_g=acid_mass_g,
        acidity_pre=acidity_pre,
        sugar_to_acid_ratio=sugar_to_acid_ratio,
        dilution_factor=dilution_factor,
        dilution_water_ml=dilution_water_ml,
        final_volume_ml=final_volume_ml,
        abv_post=abv_post,
        brix_post=brix_post,
        acidity_post=acidity_post,
    )
