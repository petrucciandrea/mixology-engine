"""Diluizione da ghiaccio di servizio: bilancio termico.

I valori attesi si calcolano a mano dalle formule del modulo, su una
ricetta d'acqua pura dove il conto si chiude con l'aritmetica:
`T_f = 0 °C`, quindi `m_eq = M · c_p,w · (T_s − T_f) / L`.
"""

from __future__ import annotations

import math
from dataclasses import replace
from itertools import pairwise

import pytest
from hypothesis import given, settings

from app.domain.entities import Ingredient, Recipe, RecipeIngredient
from app.domain.enums import DilutionMethod, IngredientCategory, ServingIce
from app.domain.errors import InvalidServingConditionsError
from app.domain.services.balance_calculator import WATER_DENSITY_G_ML, calculate_balance
from app.domain.services.serving_dilution import (
    AMBIENT_HEAT_GAIN_W,
    AMBIENT_TEMPERATURE_C,
    CP_WATER_J_G_K,
    ETHANOL_DENSITY_G_ML,
    ETHANOL_MOLAR_MASS_G_MOL,
    FREEZING_POINT_FLOOR_C,
    HEAT_TRANSFER_W_M2_K,
    ICE_DENSITY_G_ML,
    LATENT_HEAT_FUSION_J_G,
    MAX_CONSUMPTION_MINUTES,
    SUCROSE_MOLAR_MASS_G_MOL,
    calculate_serving_curve,
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


class TestServingTemperature:
    def test_built_water_cools_exponentially_towards_zero(self, water: Ingredient) -> None:
        """Senza soluti `T_f = 0 °C` a ogni diluizione: resta il transitorio puro,
        `T(t) = T_s · e^(−t/τ)`."""
        recipe = _water_recipe(water, ServingIce.LARGE_CUBE, DilutionMethod.BUILT)
        profile = calculate_serving_profile(recipe, calculate_balance(recipe), 1.0)

        assert profile is not None
        # Cubo grosso: A = 120 m⁻¹ · 1e-4 m³ = 0.012 m², τ = 418 / 3.6 ≈ 116.1 s.
        tau = 100.0 * CP_WATER_J_G_K / (HEAT_TRANSFER_W_M2_K * 120.0 * 1e-4)
        assert profile.temperature_c == pytest.approx(
            AMBIENT_TEMPERATURE_C * math.exp(-60.0 / tau), rel=1e-9
        )

    def test_a_chilled_drink_warms_as_ambient_melt_dilutes_it(self, daiquiri: Recipe) -> None:
        """Shakerato: nessun transitorio, la temperatura è il punto di
        congelamento della miscela diluita dall'acqua di fusione ambiente."""
        recipe = replace(daiquiri, serving_ice=ServingIce.CUBES)
        balance = calculate_balance(recipe)
        profile = calculate_serving_profile(recipe, balance, 10.0)

        assert profile is not None
        ethanol_g = balance.pure_alcohol_ml * ETHANOL_DENSITY_G_ML
        water_g = balance.final_mass_g - ethanol_g - balance.sugar_mass_g
        solute_mol = (
            ethanol_g / ETHANOL_MOLAR_MASS_G_MOL + balance.sugar_mass_g / SUCROSE_MOLAR_MASS_G_MOL
        )
        ambient_melt_g = profile.ambient_melt_water_ml * WATER_DENSITY_G_ML
        assert profile.temperature_c == pytest.approx(
            freezing_point_c(solute_mol, water_g + ambient_melt_g)
        )
        assert profile.initial_temperature_c < profile.temperature_c < 0.0


class TestServingIce:
    def test_the_glass_holds_as_much_ice_as_drink(self, water: Ingredient) -> None:
        recipe = _water_recipe(water, ServingIce.CUBES, DilutionMethod.BUILT)
        profile = calculate_serving_profile(recipe, calculate_balance(recipe), 10.0)

        assert profile is not None
        # 100 ml di drink → 100 ml di ghiaccio → 91.7 g.
        assert profile.ice_mass_g == pytest.approx(100.0 * ICE_DENSITY_G_ML)
        assert profile.remaining_ice_g == pytest.approx(
            profile.ice_mass_g - profile.melt_water_ml * WATER_DENSITY_G_ML
        )


class TestServingCurve:
    def test_no_ice_means_no_curve(self, daiquiri: Recipe) -> None:
        curve = calculate_serving_curve(
            daiquiri, calculate_balance(daiquiri), span_minutes=30.0, step_minutes=1.0
        )
        assert curve is None

    def test_samples_the_span_from_the_moment_of_serving(self, water: Ingredient) -> None:
        recipe = _water_recipe(water, ServingIce.CUBES, DilutionMethod.BUILT)
        curve = calculate_serving_curve(
            recipe, calculate_balance(recipe), span_minutes=30.0, step_minutes=1.0
        )

        assert curve is not None
        assert [point.consumption_minutes for point in curve] == [float(m) for m in range(31)]

    def test_the_first_point_is_the_drink_as_served(self, water: Ingredient) -> None:
        recipe = _water_recipe(water, ServingIce.CUBES, DilutionMethod.BUILT)
        balance = calculate_balance(recipe)
        curve = calculate_serving_curve(recipe, balance, span_minutes=10.0, step_minutes=2.5)

        assert curve is not None
        served = curve[0]
        assert served.melt_water_ml == 0.0
        assert served.temperature_c == pytest.approx(served.initial_temperature_c)
        assert served.abv == pytest.approx(balance.abv_post)
        assert served.remaining_ice_g == pytest.approx(served.ice_mass_g)

    def test_every_later_point_is_the_profile_at_that_minute(self, white_rum: Ingredient) -> None:
        """La curva è lo stesso modello campionato, non un'approssimazione."""
        recipe = Recipe(
            id="rum",
            name="Rum on ice",
            dilution_method=DilutionMethod.BUILT,
            serving_ice=ServingIce.CUBES,
            ingredients=(RecipeIngredient(ingredient=white_rum, volume_ml=50.0),),
        )
        balance = calculate_balance(recipe)
        curve = calculate_serving_curve(recipe, balance, span_minutes=6.0, step_minutes=1.5)

        assert curve is not None
        for point in curve[1:]:
            assert point == calculate_serving_profile(recipe, balance, point.consumption_minutes)

    @pytest.mark.parametrize(
        ("span", "step"),
        [
            (30.0, 0.0),
            (30.0, -1.0),
            (MAX_CONSUMPTION_MINUTES + 1, 1.0),
            (5.0, 10.0),
            (math.nan, 1.0),
            (30.0, math.inf),
        ],
    )
    def test_rejects_impossible_grids(self, water: Ingredient, span: float, step: float) -> None:
        recipe = _water_recipe(water, ServingIce.CUBES, DilutionMethod.BUILT)
        with pytest.raises(InvalidServingConditionsError):
            calculate_serving_curve(
                recipe, calculate_balance(recipe), span_minutes=span, step_minutes=step
            )


@given(recipe=recipes())
@settings(max_examples=200)
def test_serving_curve_only_moves_one_way(recipe: Recipe) -> None:
    """Il ghiaccio fonde e basta: l'acqua cresce, ghiaccio e ABV calano, e la
    temperatura non supera mai quella di partenza né lo zero."""
    curve = calculate_serving_curve(
        recipe, calculate_balance(recipe), span_minutes=30.0, step_minutes=1.0
    )

    if recipe.serving_ice is ServingIce.NONE:
        assert curve is None
        return

    assert curve is not None
    for before, after in pairwise(curve):
        assert after.melt_water_ml >= before.melt_water_ml - 1e-9
        assert after.remaining_ice_g <= before.remaining_ice_g + 1e-9
        assert after.abv <= before.abv + 1e-12

    for point in curve:
        assert math.isfinite(point.temperature_c)
        assert point.temperature_c >= FREEZING_POINT_FLOOR_C
        assert point.temperature_c <= max(point.initial_temperature_c, 0.0) + 1e-9
        assert 0.0 <= point.remaining_ice_g <= point.ice_mass_g


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
