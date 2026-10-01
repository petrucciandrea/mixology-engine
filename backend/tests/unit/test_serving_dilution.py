"""Diluizione da ghiaccio di servizio: bilancio termico.

I valori attesi si calcolano a mano dalle formule del modulo, su una
ricetta d'acqua pura dove il conto si chiude con l'aritmetica:
`T_f = 0 °C`, quindi `m_eq = M · c_p,w · (T_s − T_f) / L`.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
from hypothesis import given, settings

from app.domain.entities import Ingredient, Recipe, RecipeIngredient
from app.domain.enums import DilutionMethod, IngredientCategory, ServingIce
from app.domain.errors import InvalidServingConditionsError
from app.domain.services.balance_calculator import calculate_balance
from app.domain.services.serving_dilution import (
    AMBIENT_HEAT_GAIN_W,
    AMBIENT_TEMPERATURE_C,
    CP_WATER_J_G_K,
    HEAT_TRANSFER_W_M2_K,
    LATENT_HEAT_FUSION_J_G,
    MAX_CONSUMPTION_MINUTES,
    calculate_serving_profile,
    freezing_point_c,
)

from .conftest import make_ingredient
from .test_balance_properties import recipes

#: 100 ml d'acqua a 20 °C su ghiaccio a 0 °C: l'acqua da fondere per
#: raffreddarla fino a 0 °C è 100 · 4.18 · 20 / 334 g.
WATER_MELT_G = 100.0 * CP_WATER_J_G_K * AMBIENT_TEMPERATURE_C / LATENT_HEAT_FUSION_J_G


@pytest.fixture
def water() -> Ingredient:
    return make_ingredient(
        "water", "Acqua", IngredientCategory.WATER, abv=0.0, brix=0.0, acidity=0.0, density_g_ml=1.0
    )


def _water_recipe(water: Ingredient, ice: ServingIce, method: DilutionMethod) -> Recipe:
    return Recipe(
        id="water",
        name="Acqua",
        dilution_method=method,
        serving_ice=ice,
        ingredients=(RecipeIngredient(ingredient=water, volume_ml=100.0),),
    )


class TestFreezingPoint:
    def test_one_molal_solution_freezes_at_minus_kf(self) -> None:
        assert freezing_point_c(1.0, 1000.0) == pytest.approx(-1.86)

    def test_pure_water_freezes_at_zero(self) -> None:
        assert freezing_point_c(0.0, 100.0) == 0.0

    def test_is_saturated_outside_the_model_domain(self) -> None:
        assert freezing_point_c(50.0, 10.0) == -40.0


class TestServingProfile:
    def test_no_ice_means_no_serving_profile(self, daiquiri: Recipe) -> None:
        """`None` e non zero: "non applicabile" non è "diluizione nulla"."""
        assert daiquiri.serving_ice is ServingIce.NONE
        assert calculate_serving_profile(daiquiri, calculate_balance(daiquiri), 10.0) is None

    @pytest.mark.parametrize(
        "minutes", [0.0, -1.0, MAX_CONSUMPTION_MINUTES + 1, math.nan, math.inf]
    )
    def test_rejects_impossible_consumption_times(self, daiquiri: Recipe, minutes: float) -> None:
        with pytest.raises(InvalidServingConditionsError):
            calculate_serving_profile(daiquiri, calculate_balance(daiquiri), minutes)

    def test_chilled_drink_only_gains_ambient_melt(self, daiquiri: Recipe) -> None:
        """Un drink shakerato esce già all'equilibrio: nessun raffreddamento."""
        recipe = replace(daiquiri, serving_ice=ServingIce.CUBES)
        profile = calculate_serving_profile(recipe, calculate_balance(recipe), 10.0)

        assert profile is not None
        assert profile.cooling_melt_water_ml == 0.0
        assert profile.ambient_melt_water_ml == pytest.approx(
            AMBIENT_HEAT_GAIN_W * 600.0 / LATENT_HEAT_FUSION_J_G
        )
        assert profile.initial_temperature_c == pytest.approx(profile.equilibrium_temperature_c)
        assert profile.initial_temperature_c < 0.0

    def test_built_drink_melts_ice_to_reach_equilibrium(self, water: Ingredient) -> None:
        recipe = _water_recipe(water, ServingIce.CUBES, DilutionMethod.BUILT)
        profile = calculate_serving_profile(recipe, calculate_balance(recipe), 60.0)

        assert profile is not None
        assert profile.initial_temperature_c == AMBIENT_TEMPERATURE_C
        assert profile.equilibrium_temperature_c == pytest.approx(0.0)
        # A 60 minuti il transitorio è esaurito: resta l'acqua di equilibrio.
        assert profile.cooling_melt_water_ml == pytest.approx(WATER_MELT_G, rel=1e-6)

    def test_cooling_conserves_energy_on_a_solute_drink(self, white_rum: Ingredient) -> None:
        """m·(L − c_w·|T_f|) = M·c_p·(T_s − T_f), con la bisezione a convergenza."""
        recipe = Recipe(
            id="rum",
            name="Rum on ice",
            dilution_method=DilutionMethod.BUILT,
            serving_ice=ServingIce.CRUSHED,
            ingredients=(RecipeIngredient(ingredient=white_rum, volume_ml=50.0),),
        )
        balance = calculate_balance(recipe)
        profile = calculate_serving_profile(recipe, balance, MAX_CONSUMPTION_MINUTES)

        assert profile is not None
        t_final = profile.equilibrium_temperature_c
        melt = profile.cooling_melt_water_ml
        # c_p del rum 40%: 20 ml etanolo puro (15.78 g) e 31.0 g d'acqua.
        ethanol_g = 50.0 * 0.40 * 0.789
        water_g = 50.0 * 0.95 - ethanol_g
        cp = (ethanol_g * 2.44 + water_g * 4.18) / (ethanol_g + water_g)
        released = balance.final_mass_g * cp * (AMBIENT_TEMPERATURE_C - t_final)
        absorbed = melt * (LATENT_HEAT_FUSION_J_G - CP_WATER_J_G_K * abs(t_final))
        assert absorbed == pytest.approx(released, rel=1e-3)

    def test_ice_type_sets_the_speed_of_cooling(self, water: Ingredient) -> None:
        """Il tipo agisce su τ = M·c_p / (h·S/V·V_ghiaccio), non sull'equilibrio."""
        recipes_by_ice = {
            ice: _water_recipe(water, ice, DilutionMethod.BUILT)
            for ice in (ServingIce.CRUSHED, ServingIce.CUBES, ServingIce.LARGE_CUBE)
        }
        melt = {}
        for ice, recipe in recipes_by_ice.items():
            profile = calculate_serving_profile(recipe, calculate_balance(recipe), 1.0)
            assert profile is not None
            melt[ice] = profile.cooling_melt_water_ml

        assert melt[ServingIce.CRUSHED] > melt[ServingIce.CUBES] > melt[ServingIce.LARGE_CUBE]

        # Cubo grosso: S/V = 120 m⁻¹, V_ghiaccio = 100 ml = 1e-4 m³ → A = 0.012 m².
        tau = 100.0 * CP_WATER_J_G_K / (HEAT_TRANSFER_W_M2_K * 120.0 * 1e-4)
        assert melt[ServingIce.LARGE_CUBE] == pytest.approx(
            WATER_MELT_G * (1.0 - math.exp(-60.0 / tau)), rel=1e-6
        )

    def test_diluted_profile_is_consistent_with_the_melt(self, water: Ingredient) -> None:
        recipe = _water_recipe(water, ServingIce.CUBES, DilutionMethod.BUILT)
        balance = calculate_balance(recipe)
        profile = calculate_serving_profile(recipe, balance, 10.0)

        assert profile is not None
        assert profile.final_volume_ml == pytest.approx(100.0 + profile.melt_water_ml)
        assert profile.total_dilution_factor == pytest.approx(profile.melt_water_ml / 100.0)
        assert profile.melt_water_ml == pytest.approx(
            profile.cooling_melt_water_ml + profile.ambient_melt_water_ml
        )


@given(recipe=recipes())
@settings(max_examples=300)
def test_serving_dilution_obeys_the_physics(recipe: Recipe) -> None:
    """Finito, non negativo, mai oltre il ghiaccio disponibile, mai più concentrato."""
    balance = calculate_balance(recipe)
    profile = calculate_serving_profile(recipe, balance, 10.0)

    if recipe.serving_ice is ServingIce.NONE:
        assert profile is None
        return

    assert profile is not None
    for value in (
        profile.melt_water_ml,
        profile.final_volume_ml,
        profile.abv,
        profile.brix,
        profile.acidity,
        profile.equilibrium_temperature_c,
    ):
        assert math.isfinite(value)

    assert profile.melt_water_ml >= 0.0
    assert profile.melt_water_ml <= balance.final_volume_ml * 0.917 * (1.0 + 1e-9)
    assert profile.equilibrium_temperature_c <= 0.0
    assert profile.abv <= balance.abv_post + 1e-12
    assert profile.brix <= balance.brix_post + 1e-9
    assert profile.acidity <= balance.acidity_post + 1e-9
