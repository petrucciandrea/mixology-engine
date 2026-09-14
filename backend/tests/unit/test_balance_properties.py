"""Test property-based sulle invarianti fisiche del bilanciamento.

Un test a esempi verifica il modello sui casi a cui abbiamo pensato.
Queste proprietà lo verificano su migliaia di ricette generate, comprese
quelle a cui non avremmo pensato: densità al limite, ricette di un solo
ingrediente, dosaggi da 0.1 ml, alcol puro, sciroppi al 100 °Bx.

Ogni proprietà qui sotto è una legge fisica, non una convenzione del
codice: se una di esse cade, il modello è sbagliato, non il test.
"""

from __future__ import annotations

import math

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.domain.entities import (
    MAX_ACIDITY_PERCENT,
    MAX_BRIX,
    MAX_DENSITY_G_ML,
    MIN_DENSITY_G_ML,
    Ingredient,
    PhysicalProfile,
    Recipe,
    RecipeIngredient,
)
from app.domain.enums import DilutionMethod, IngredientCategory
from app.domain.services.balance_calculator import calculate_balance

# --- Strategie -------------------------------------------------------------

physical_profiles = st.builds(
    PhysicalProfile,
    density_g_ml=st.floats(MIN_DENSITY_G_ML, MAX_DENSITY_G_ML, allow_nan=False),
    brix=st.floats(0.0, MAX_BRIX, allow_nan=False),
    acidity=st.floats(0.0, MAX_ACIDITY_PERCENT, allow_nan=False),
    abv=st.floats(0.0, 1.0, allow_nan=False),
)


@st.composite
def recipes(draw: st.DrawFn, min_ingredients: int = 1, max_ingredients: int = 6) -> Recipe:
    """Ricette arbitrarie ma fisicamente sensate.

    Gli id sono generati per indice invece che casualmente: l'aggregate
    rifiuta gli ingredienti duplicati, e id distinti per costruzione
    evitano di scartare metà dei casi generati.
    """
    count = draw(st.integers(min_ingredients, max_ingredients))
    items = []
    for index in range(count):
        profile = draw(physical_profiles)
        volume = draw(st.floats(0.1, 300.0, allow_nan=False, allow_infinity=False))
        items.append(
            RecipeIngredient(
                ingredient=Ingredient(
                    id=f"ingredient-{index}",
                    name=f"Ingredient {index}",
                    category=draw(st.sampled_from(list(IngredientCategory))),
                    physical_profile=profile,
                ),
                volume_ml=volume,
            )
        )
    return Recipe(
        id="generated",
        name="Generated Recipe",
        dilution_method=draw(st.sampled_from(list(DilutionMethod))),
        ingredients=tuple(items),
    )


# --- Proprietà -------------------------------------------------------------


@given(recipe=recipes())
@settings(max_examples=300)
def test_every_quantity_is_finite(recipe: Recipe) -> None:
    """Nessuna formula produce NaN o infinito su input validi.

    È la proprietà più importante: un NaN non fa fallire il calcolo, si
    propaga in silenzio fino a un volume assurdo in un bicchiere.
    """
    profile = calculate_balance(recipe)
    for value in (
        profile.total_volume_ml,
        profile.pure_alcohol_ml,
        profile.total_mass_g,
        profile.sugar_mass_g,
        profile.acid_mass_g,
        profile.abv_pre,
        profile.brix_pre,
        profile.acidity_pre,
        profile.dilution_factor,
        profile.dilution_water_ml,
        profile.final_volume_ml,
        profile.final_mass_g,
        profile.abv_post,
        profile.brix_post,
        profile.acidity_post,
    ):
        assert math.isfinite(value)
    if profile.sugar_acid_ratio is not None:
        assert math.isfinite(profile.sugar_acid_ratio)


@given(recipe=recipes())
@settings(max_examples=300)
def test_abv_is_always_a_valid_fraction(recipe: Recipe) -> None:
    """L'alcol non può superare il volume che lo contiene."""
    profile = calculate_balance(recipe)
    assert 0.0 <= profile.abv_pre <= 1.0
    assert 0.0 <= profile.abv_post <= 1.0


@given(recipe=recipes())
@settings(max_examples=300)
def test_dilution_never_removes_liquid(recipe: Recipe) -> None:
    """Il ghiaccio aggiunge acqua: il volume finale non può diminuire.

    Vale anche nei casi limite in cui la curva quadratica di Arnold si
    avvicina allo zero, perché su [0, 1] entrambe le curve restano non
    negative.
    """
    profile = calculate_balance(recipe)
    assert profile.dilution_water_ml >= 0.0
    assert profile.final_volume_ml >= profile.total_volume_ml
    assert profile.final_mass_g >= profile.total_mass_g


@given(recipe=recipes())
@settings(max_examples=300)
def test_dilution_never_concentrates(recipe: Recipe) -> None:
    """Aggiungere acqua non può aumentare una concentrazione.

    Le tre grandezze intensive possono solo scendere o restare uguali
    (quest'ultimo caso solo per il metodo BUILT, che non diluisce).
    """
    profile = calculate_balance(recipe)
    assert profile.abv_post <= profile.abv_pre + 1e-12
    assert profile.brix_post <= profile.brix_pre + 1e-12
    assert profile.acidity_post <= profile.acidity_pre + 1e-12


@given(recipe=recipes())
@settings(max_examples=300)
def test_solute_mass_is_conserved_under_dilution(recipe: Recipe) -> None:
    """L'acqua diluisce, non fa sparire zuccheri e acidi.

    La massa dei soluti calcolata dalle concentrazioni post-diluizione
    deve coincidere con quella pre-diluizione: è la conservazione della
    massa applicata al modello.
    """
    profile = calculate_balance(recipe)
    sugar_after = profile.brix_post / 100.0 * profile.final_mass_g
    acid_after = profile.acidity_post / 100.0 * profile.final_mass_g

    assert sugar_after == pytest_approx(profile.sugar_mass_g)
    assert acid_after == pytest_approx(profile.acid_mass_g)


@given(recipe=recipes())
@settings(max_examples=300)
def test_alcohol_volume_is_conserved_under_dilution(recipe: Recipe) -> None:
    """Lo stesso per l'alcol, che si misura in volume e non in massa."""
    profile = calculate_balance(recipe)
    alcohol_after = profile.abv_post * profile.final_volume_ml
    assert alcohol_after == pytest_approx(profile.pure_alcohol_ml)


@given(recipe=recipes(), factor=st.floats(0.2, 5.0, allow_nan=False))
@settings(max_examples=200)
def test_scaling_all_volumes_preserves_every_intensive_quantity(
    recipe: Recipe, factor: float
) -> None:
    """Raddoppiare la ricetta raddoppia il drink, non lo rende più forte.

    È la proprietà che giustifica l'ancora proporzionale del solver: se il
    solo obiettivo è il volume finale, la soluzione esatta è un
    riscalamento uniforme, perché ABV, Brix e acidità sono invarianti.
    """
    scaled = recipe.with_volumes(tuple(volume * factor for volume in recipe.volumes_ml))

    original = calculate_balance(recipe)
    resized = calculate_balance(scaled)

    assert resized.abv_pre == pytest_approx(original.abv_pre)
    assert resized.brix_pre == pytest_approx(original.brix_pre)
    assert resized.acidity_pre == pytest_approx(original.acidity_pre)
    assert resized.dilution_factor == pytest_approx(original.dilution_factor)
    assert resized.final_volume_ml == pytest_approx(original.final_volume_ml * factor)


@given(recipe=recipes())
@settings(max_examples=200)
def test_sugar_acid_ratio_is_invariant_under_dilution(recipe: Recipe) -> None:
    """Acqua e zuccheri scalano insieme: il rapporto non si muove."""
    profile = calculate_balance(recipe)
    assume(profile.sugar_acid_ratio is not None)
    assume(profile.acidity_post > 1e-9)

    assert profile.brix_post / profile.acidity_post == pytest_approx(profile.sugar_acid_ratio)


def pytest_approx(expected: float | None) -> object:
    """Tolleranza relativa unica per tutte le proprietà.

    Le grandezze in gioco vanno da 10⁻³ (acidità di un drink poco acido) a
    10³ (massa di un punch): una tolleranza assoluta sarebbe troppo lasca
    a un estremo e troppo stretta all'altro. Il termine assoluto copre i
    valori vicini allo zero, dove quello relativo perde significato.
    """
    import pytest

    assert expected is not None
    return pytest.approx(expected, rel=1e-9, abs=1e-12)
