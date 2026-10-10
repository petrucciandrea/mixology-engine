"""Diluizione da ghiaccio di servizio: bilancio termico a due nodi.

Il modello è un'equazione differenziale (ambiente → drink → ghiaccio) e non
ha una soluzione chiusa, ma ha una legge di conservazione esatta che si
scrive a mano: con l'acqua liquida a 0 °C come riferimento, l'entalpia di
drink e ghiaccio cresce solo del calore entrato dall'ambiente,

    (C₀ + m·c_w)·T + L·m − C₀·T_s = Q_amb

dove `C₀` è la capacità termica del drink appena servito, `m` l'acqua di
fusione, `T_s` la temperatura di servizio. È il controllo principale degli
esempi e delle proprietà; gli altri verificano i regimi che si ricavano a
mano dalle equazioni (regime quasi stazionario, ghiaccio esaurito) e le
tendenze che il tipo di ghiaccio deve produrre.
"""

from __future__ import annotations

import math
from dataclasses import replace
from itertools import pairwise

import pytest
from hypothesis import given, settings

from app.domain.balance import BalanceProfile, ServingProfile
from app.domain.entities import Ingredient, Recipe, RecipeIngredient
from app.domain.enums import DilutionMethod, IngredientCategory, ServingIce
from app.domain.errors import InvalidServingConditionsError
from app.domain.services.balance_calculator import WATER_DENSITY_G_ML, calculate_balance
from app.domain.services.serving_dilution import (
    AMBIENT_TEMPERATURE_C,
    CP_ETHANOL_J_G_K,
    CP_SUGAR_J_G_K,
    CP_WATER_J_G_K,
    ETHANOL_DENSITY_G_ML,
    ETHANOL_MOLAR_MASS_G_MOL,
    FREEZING_POINT_FLOOR_C,
    GLASS_HEAT_TRANSFER_W_K,
    HEAT_TRANSFER_W_M2_K,
    ICE_DENSITY_G_ML,
    LATENT_HEAT_FUSION_J_G,
    MAX_CONSUMPTION_MINUTES,
    SUCROSE_MOLAR_MASS_G_MOL,
    calculate_serving_curve,
    calculate_serving_profile,
    freezing_point_c,
)
from app.domain.serving_geometry import ICE_PIECES

from .conftest import make_ingredient
from .test_balance_properties import recipes


@pytest.fixture
def water() -> Ingredient:
    return make_ingredient(
        "water", "Acqua", IngredientCategory.WATER, abv=0.0, brix=0.0, acidity=0.0, density_g_ml=1.0
    )


def _water_recipe(
    water: Ingredient, ice: ServingIce, method: DilutionMethod, volume_ml: float = 100.0
) -> Recipe:
    return Recipe(
        id="water",
        name="Acqua",
        dilution_method=method,
        serving_ice=ice,
        ingredients=(RecipeIngredient(ingredient=water, volume_ml=volume_ml),),
    )


def _served(recipe: Recipe, minutes: float) -> tuple[BalanceProfile, ServingProfile]:
    balance = calculate_balance(recipe)
    profile = calculate_serving_profile(recipe, balance, minutes)
    assert profile is not None
    return balance, profile


def _water_g(balance: BalanceProfile) -> float:
    """Acqua del drink (acidi compresi): la massa che resta tolti etanolo e
    zucchero, mai negativa anche per un profilo al limite del plausibile."""
    ethanol_g = balance.pure_alcohol_ml * ETHANOL_DENSITY_G_ML
    return max(balance.final_mass_g - ethanol_g - balance.sugar_mass_g, 0.0)


def _heat_capacity_j_k(balance: BalanceProfile) -> float:
    """C₀ = Σ mᵢ·cᵢ su etanolo, zucchero e acqua (gli acidi contano come acqua)."""
    ethanol_g = balance.pure_alcohol_ml * ETHANOL_DENSITY_G_ML
    water_g = _water_g(balance)
    return (
        ethanol_g * CP_ETHANOL_J_G_K
        + balance.sugar_mass_g * CP_SUGAR_J_G_K
        + water_g * CP_WATER_J_G_K
    )


def _enthalpy_gain_j(balance: BalanceProfile, profile: ServingProfile) -> float:
    """Membro sinistro della legge di conservazione."""
    c0 = _heat_capacity_j_k(balance)
    melt_g = profile.melt_water_ml * WATER_DENSITY_G_ML
    return (
        (c0 + melt_g * CP_WATER_J_G_K) * profile.temperature_c
        + LATENT_HEAT_FUSION_J_G * melt_g
        - c0 * profile.initial_temperature_c
    )


def _freezing_point_of(balance: BalanceProfile, melt_ml: float) -> float:
    ethanol_g = balance.pure_alcohol_ml * ETHANOL_DENSITY_G_ML
    water_g = _water_g(balance)
    solute_mol = (
        ethanol_g / ETHANOL_MOLAR_MASS_G_MOL + balance.sugar_mass_g / SUCROSE_MOLAR_MASS_G_MOL
    )
    return freezing_point_c(solute_mol, water_g + melt_ml * WATER_DENSITY_G_ML)


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

    def test_a_chilled_drink_starts_at_its_freezing_point(self, daiquiri: Recipe) -> None:
        """Shaken e stirred escono dalla preparazione all'equilibrio con il
        proprio ghiaccio; un built nasce a temperatura ambiente."""
        _, shaken = _served(replace(daiquiri, serving_ice=ServingIce.CUBES), 1.0)
        balance, _ = _served(replace(daiquiri, serving_ice=ServingIce.CUBES), 1.0)
        assert shaken.initial_temperature_c == pytest.approx(_freezing_point_of(balance, 0.0))

        built = replace(
            daiquiri, serving_ice=ServingIce.CUBES, dilution_method=DilutionMethod.BUILT
        )
        assert _served(built, 1.0)[1].initial_temperature_c == AMBIENT_TEMPERATURE_C

    @pytest.mark.parametrize("ice", [ServingIce.CUBES, ServingIce.LARGE_CUBE, ServingIce.CRUSHED])
    @pytest.mark.parametrize("method", [DilutionMethod.BUILT, DilutionMethod.SHAKEN])
    def test_enthalpy_grows_only_by_the_heat_from_the_room(
        self, white_rum: Ingredient, ice: ServingIce, method: DilutionMethod
    ) -> None:
        recipe = Recipe(
            id="rum",
            name="Rum on ice",
            dilution_method=method,
            serving_ice=ice,
            ingredients=(RecipeIngredient(ingredient=white_rum, volume_ml=50.0),),
        )
        balance, profile = _served(recipe, 10.0)

        assert profile.ambient_heat_j > 0.0
        assert _enthalpy_gain_j(balance, profile) == pytest.approx(
            profile.ambient_heat_j, rel=1e-9, abs=1e-6
        )

    def test_the_room_heats_through_the_glass(self, water: Ingredient) -> None:
        """Il calore ambiente è U·(T_a − T) integrato nel tempo: per un drink
        che resta sul ghiaccio a ~0 °C è circa U·T_a·t, non una costante."""
        _, profile = _served(_water_recipe(water, ServingIce.CRUSHED, DilutionMethod.SHAKEN), 10.0)

        # Acqua pura: T ≈ 0 °C per tutto il tempo, quindi Q ≈ 0.3 · 20 · 600 = 3600 J.
        assert profile.ambient_heat_j == pytest.approx(
            GLASS_HEAT_TRANSFER_W_K * AMBIENT_TEMPERATURE_C * 600.0, rel=0.02
        )

    def test_a_built_drink_is_brought_to_its_freezing_point(self, water: Ingredient) -> None:
        """Acqua a 20 °C su tritato: dopo 10 minuti il raffreddamento è
        esaurito e il drink sta appena sopra il proprio punto di congelamento."""
        _, profile = _served(_water_recipe(water, ServingIce.CRUSHED, DilutionMethod.BUILT), 10.0)

        assert profile.freezing_point_c == 0.0
        assert 0.0 < profile.temperature_c < 0.5
        # Quasi tutto il calore sensibile del drink è diventato fusione:
        # 100 · 4.18 · 20 / 334 = 25.0 g, più quanto ha portato l'ambiente.
        assert profile.melt_water_ml > 100.0 * CP_WATER_J_G_K * 20.0 / LATENT_HEAT_FUSION_J_G

    def test_on_ice_the_drink_settles_where_the_ice_takes_what_the_room_gives(
        self, water: Ingredient
    ) -> None:
        """Regime quasi stazionario: il calore che entra dal vetro esce verso
        il ghiaccio, U·(T_a − T) = h·A·(T − T_f), quindi lo scarto dal punto
        di congelamento è U·(T_a − T) / (h·A), con A la superficie residua.

        L'acqua di fusione entra a `T_f` e va scaldata: a regime tutto il
        calore del vetro diventa fusione, ṁ = U·(T_a − T)/L, e si aggiunge
        una conduttanza ṁ·c_w accanto a h·A.

        Acqua pura perché `T_f` resti 0 °C: con dei soluti la diluizione
        alza `T_f` e il drink lo insegue, un termine `C·dT/dt` che la
        formula trascura. Resta trascurata solo la deriva lenta dovuta alla
        superficie che cala, sotto l'1%."""
        recipe = _water_recipe(water, ServingIce.CUBES, DilutionMethod.SHAKEN)
        balance, profile = _served(recipe, 20.0)

        piece = ICE_PIECES[ServingIce.CUBES]
        ice_volume_m3 = balance.final_volume_ml * 1e-6
        left = profile.remaining_ice_g / profile.ice_mass_g
        area = piece.specific_surface_m2_per_m3 * ice_volume_m3 * left ** (2.0 / 3.0)
        from_room = GLASS_HEAT_TRANSFER_W_K * (AMBIENT_TEMPERATURE_C - profile.temperature_c)
        melt_rate = from_room / LATENT_HEAT_FUSION_J_G
        expected = from_room / (HEAT_TRANSFER_W_M2_K * area + melt_rate * CP_WATER_J_G_K)
        assert profile.freezing_point_c == 0.0
        assert profile.temperature_c == pytest.approx(expected, rel=0.01)

    def test_diluted_profile_is_consistent_with_the_melt(self, water: Ingredient) -> None:
        recipe = _water_recipe(water, ServingIce.CUBES, DilutionMethod.BUILT)
        balance, profile = _served(recipe, 10.0)

        assert profile.final_volume_ml == pytest.approx(100.0 + profile.melt_water_ml)
        assert profile.total_dilution_factor == pytest.approx(profile.melt_water_ml / 100.0)
        assert profile.freezing_point_c == pytest.approx(
            _freezing_point_of(balance, profile.melt_water_ml)
        )


class TestIceType:
    """Il tipo di ghiaccio decide la superficie di scambio drink → ghiaccio:
    quanto in fretta un drink caldo si raffredda e, una volta freddo, quanto
    sta sopra il proprio punto di congelamento. Un drink più freddo assorbe
    più calore dall'ambiente, e quindi fonde più ghiaccio."""

    def test_finer_ice_chills_a_built_drink_faster(self, water: Ingredient) -> None:
        temperature = {}
        melt = {}
        for ice in (ServingIce.CRUSHED, ServingIce.CUBES, ServingIce.LARGE_CUBE):
            _, profile = _served(_water_recipe(water, ice, DilutionMethod.BUILT), 1.0)
            temperature[ice] = profile.temperature_c
            melt[ice] = profile.melt_water_ml

        crushed, cubes, large = ServingIce.CRUSHED, ServingIce.CUBES, ServingIce.LARGE_CUBE
        assert temperature[crushed] < temperature[cubes] < temperature[large]
        assert melt[crushed] > melt[cubes] > melt[large]

    def test_finer_ice_keeps_a_chilled_drink_colder_and_dilutes_it_more(
        self, daiquiri: Recipe
    ) -> None:
        """Il caso che il modello precedente non vedeva: uno shakerato su
        cubetti e su tritato. Stessa massa di ghiaccio, superficie diversa."""
        crushed = _served(replace(daiquiri, serving_ice=ServingIce.CRUSHED), 30.0)[1]
        cubes = _served(replace(daiquiri, serving_ice=ServingIce.CUBES), 30.0)[1]

        assert crushed.ice_mass_g == pytest.approx(cubes.ice_mass_g)
        assert crushed.temperature_c < cubes.temperature_c
        assert crushed.melt_water_ml > cubes.melt_water_ml

    def test_a_single_piece_leaves_a_chilled_drink_warmer(self, daiquiri: Recipe) -> None:
        large = _served(replace(daiquiri, serving_ice=ServingIce.LARGE_CUBE), 30.0)[1]
        cubes = _served(replace(daiquiri, serving_ice=ServingIce.CUBES), 30.0)[1]

        assert large.temperature_c > cubes.temperature_c


class TestServingIce:
    @pytest.mark.parametrize("ice", [ServingIce.CUBES, ServingIce.CRUSHED])
    def test_fill_ice_follows_the_drink(self, water: Ingredient, ice: ServingIce) -> None:
        _, profile = _served(_water_recipe(water, ice, DilutionMethod.BUILT), 10.0)
        # 100 ml di drink → 100 ml di ghiaccio → 91.7 g.
        assert profile.ice_mass_g == pytest.approx(100.0 * ICE_DENSITY_G_ML)

    @pytest.mark.parametrize(
        ("ice", "volume_ml"), [(ServingIce.LARGE_CUBE, 125.0), (ServingIce.SPEAR, 108.0)]
    )
    @pytest.mark.parametrize("drink_ml", [40.0, 200.0])
    def test_a_single_piece_weighs_the_same_whatever_the_drink(
        self, water: Ingredient, ice: ServingIce, volume_ml: float, drink_ml: float
    ) -> None:
        recipe = _water_recipe(water, ice, DilutionMethod.SHAKEN, volume_ml=drink_ml)
        _, profile = _served(recipe, 10.0)
        assert profile.ice_mass_g == pytest.approx(volume_ml * ICE_DENSITY_G_ML)

    def test_the_remaining_ice_is_what_did_not_melt(self, water: Ingredient) -> None:
        _, profile = _served(_water_recipe(water, ServingIce.CUBES, DilutionMethod.BUILT), 10.0)
        assert profile.remaining_ice_g == pytest.approx(
            profile.ice_mass_g - profile.melt_water_ml * WATER_DENSITY_G_ML
        )

    def test_once_the_ice_is_gone_the_drink_warms_towards_the_room(self, water: Ingredient) -> None:
        """10 ml d'acqua su 9.2 g di tritato: l'ambiente porta ~0.3·20 W, e
        per fondere tutto ne bastano 9.17 · 334 ≈ 3.1 kJ, cioè ~9 minuti.
        Dopo, il drink si scalda: senza ghiaccio resta solo il vetro."""
        recipe = _water_recipe(water, ServingIce.CRUSHED, DilutionMethod.SHAKEN, volume_ml=10.0)
        balance, profile = _served(recipe, MAX_CONSUMPTION_MINUTES)

        assert profile.remaining_ice_g == 0.0
        assert profile.melt_water_ml * WATER_DENSITY_G_ML == pytest.approx(profile.ice_mass_g)
        assert 0.0 < profile.temperature_c < AMBIENT_TEMPERATURE_C
        assert _enthalpy_gain_j(balance, profile) == pytest.approx(profile.ambient_heat_j)


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
        assert served.ambient_heat_j == 0.0
        assert served.temperature_c == pytest.approx(served.initial_temperature_c)
        assert served.abv == pytest.approx(balance.abv_post)
        assert served.remaining_ice_g == pytest.approx(served.ice_mass_g)

    def test_every_later_point_is_the_profile_at_that_minute(self, white_rum: Ingredient) -> None:
        """La curva è lo stesso modello campionato, non un'approssimazione:
        l'integrazione avanza su una griglia fissa, quindi un campione e un
        profilo allo stesso minuto fanno esattamente gli stessi passi."""
        recipe = Recipe(
            id="rum",
            name="Rum on ice",
            dilution_method=DilutionMethod.BUILT,
            serving_ice=ServingIce.SPEAR,
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
@settings(max_examples=150, deadline=None)
def test_serving_curve_only_moves_one_way(recipe: Recipe) -> None:
    """Il ghiaccio fonde e basta: l'acqua cresce, ghiaccio e ABV calano, il
    calore ambiente si accumula. La temperatura resta fra il pavimento del
    modello crioscopico e la più alta fra quella di servizio e l'ambiente."""
    balance = calculate_balance(recipe)
    curve = calculate_serving_curve(recipe, balance, span_minutes=30.0, step_minutes=1.0)

    if recipe.serving_ice is ServingIce.NONE:
        assert curve is None
        return

    assert curve is not None
    for before, after in pairwise(curve):
        assert after.melt_water_ml >= before.melt_water_ml
        assert after.remaining_ice_g <= before.remaining_ice_g + 1e-9
        assert after.abv <= before.abv + 1e-12

    for point in curve:
        assert math.isfinite(point.temperature_c)
        assert FREEZING_POINT_FLOOR_C <= point.temperature_c <= AMBIENT_TEMPERATURE_C + 1e-9
        assert 0.0 <= point.remaining_ice_g <= point.ice_mass_g
        assert _enthalpy_gain_j(balance, point) == pytest.approx(
            point.ambient_heat_j, rel=1e-6, abs=1e-6
        )


@given(recipe=recipes())
@settings(max_examples=150, deadline=None)
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
        profile.freezing_point_c,
        profile.ambient_heat_j,
    ):
        assert math.isfinite(value)

    assert profile.melt_water_ml >= 0.0
    assert profile.melt_water_ml * WATER_DENSITY_G_ML <= profile.ice_mass_g * (1.0 + 1e-9)
    assert profile.freezing_point_c <= 0.0
    assert profile.abv <= balance.abv_post + 1e-12
    assert profile.brix <= balance.brix_post + 1e-9
    assert profile.acidity <= balance.acidity_post + 1e-9
