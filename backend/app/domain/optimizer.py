from __future__ import annotations

from typing import cast

import numpy as np
from pydantic import BaseModel
from scipy.optimize import minimize

from .calculator import calculate_recipe_profile
from .models import Recipe, RecipeIngredient


class TargetProfile(BaseModel):
    target_abv: float | None = None
    target_brix: float | None = None
    target_acidity: float | None = None
    target_ratio: float | None = None
    target_volume_ml: float | None = None


def _build_recipe_with_volumes(base_recipe: Recipe, volumes: list[float]) -> Recipe:
    ingredienti = [
        RecipeIngredient(
            ingrediente=recipe_ingredient.ingrediente,
            volume_ml=volume,
        )
        for recipe_ingredient, volume in zip(
            base_recipe.ingredienti,
            volumes,
            strict=True,
        )
    ]
    return Recipe(
        id=base_recipe.id,
        nome=base_recipe.nome,
        ingredienti=ingredienti,
        dilution_method=base_recipe.dilution_method,
    )


def _relative_squared_error(actual: float | None, target: float) -> float:
    if actual is None:
        return 1_000_000.0

    denominator = max(abs(target), 1e-6)
    discrepancy = (actual - target) / denominator
    return discrepancy**2


def _objective_function(volumes: np.ndarray, base_recipe: Recipe, target: TargetProfile) -> float:
    recipe = _build_recipe_with_volumes(base_recipe, volumes.tolist())
    profile = calculate_recipe_profile(recipe)

    weighted_errors: list[float] = []

    if target.target_abv is not None:
        weighted_errors.append(_relative_squared_error(profile.abv_post, target.target_abv))
    if target.target_brix is not None:
        weighted_errors.append(_relative_squared_error(profile.brix_post, target.target_brix))
    if target.target_acidity is not None:
        weighted_errors.append(
            _relative_squared_error(profile.acidity_post, target.target_acidity)
        )
    if target.target_ratio is not None:
        weighted_errors.append(
            _relative_squared_error(profile.sugar_to_acid_ratio, target.target_ratio)
        )
    if target.target_volume_ml is not None:
        weighted_errors.append(
            0.5 * _relative_squared_error(profile.final_volume_ml, target.target_volume_ml)
        )

    return float(sum(weighted_errors))


def optimize_recipe_volumes(
    base_recipe: Recipe,
    target: TargetProfile,
    min_volume: float = 5.0,
    max_volume: float = 120.0,
) -> Recipe:
    if min_volume <= 0:
        raise ValueError("min_volume must be greater than 0")
    if max_volume < min_volume:
        raise ValueError("max_volume must be greater than or equal to min_volume")

    active_targets = [
        target.target_abv,
        target.target_brix,
        target.target_acidity,
        target.target_ratio,
        target.target_volume_ml,
    ]
    if all(value is None for value in active_targets):
        raise ValueError("at least one target value must be provided")

    initial_volumes = np.array(
        [recipe_ingredient.volume_ml for recipe_ingredient in base_recipe.ingredienti],
        dtype=float,
    )
    clipped_initial_volumes = np.clip(initial_volumes, min_volume, max_volume)
    bounds = [(min_volume, max_volume)] * len(base_recipe.ingredienti)

    result = minimize(
        _objective_function,
        x0=clipped_initial_volumes,
        args=(base_recipe, target),
        method="SLSQP",
        bounds=bounds,
    )

    if result.x is None or not np.all(np.isfinite(result.x)):
        optimized_volumes = clipped_initial_volumes
    else:
        optimized_volumes = np.clip(result.x, min_volume, max_volume)

    rounded_volumes = [round(float(volume), 1) for volume in optimized_volumes.tolist()]
    return _build_recipe_with_volumes(base_recipe, cast(list[float], rounded_volumes))
