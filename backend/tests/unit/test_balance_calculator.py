"""Verifica delle formule di bilanciamento e diluizione.

I valori attesi sono calcolati a mano dalle formule del domain model, non
copiati da un'esecuzione del codice: un test che si limita a fotografare
l'output conferma solo che il codice non è cambiato, non che è corretto.
"""

from __future__ import annotations

import pytest

from app.domain.balance import SOUR_RATIO_LOWER_BOUND, SOUR_RATIO_UPPER_BOUND
from app.domain.entities import Ingredient, Recipe, RecipeIngredient
from app.domain.enums import DilutionMethod, ServingIce
from app.domain.services import dilution
from app.domain.services.balance_calculator import calculate_balance, sugar_acid_ratio


class TestDilutionModel:
    """Le due curve di Dave Arnold."""

    def test_shaken_factor_matches_published_quadratic(self) -> None:
        # -1.567·0.0784 + 1.742·0.28 + 0.203 = -0.1228528 + 0.48776 + 0.203
        assert dilution.shaken_dilution_factor(0.28) == pytest.approx(0.5679072, abs=1e-7)

    def test_stirred_factor_matches_published_quadratic(self) -> None:
        # -1.150·0.0784 + 1.350·0.28 + 0.150 = -0.09016 + 0.378 + 0.150
        assert dilution.stirred_dilution_factor(0.28) == pytest.approx(0.43784, abs=1e-7)

    def test_shaking_dilutes_more_than_stirring_at_every_realistic_abv(self) -> None:
        """L'agitazione immette più energia: a parità di gradazione scioglie più ghiaccio."""
        for abv in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
            assert dilution.shaken_dilution_factor(abv) > dilution.stirred_dilution_factor(abv)

    def test_zero_alcohol_still_dilutes(self) -> None:
        """Un analcolico shakerato prende comunque il 20.3% d'acqua.

        Non è un bug: l'intercetta della regressione è fisica, perché lo
        scambio termico con il ghiaccio avviene indipendentemente
        dall'alcol. Il test esiste per fissare l'intenzione, così nessuno
        lo "corregge" scambiandolo per un errore.
        """
        assert dilution.shaken_dilution_factor(0.0) == pytest.approx(0.203)
        assert dilution.stirred_dilution_factor(0.0) == pytest.approx(0.150)

    def test_built_method_has_no_preparation_dilution(self) -> None:
        assert dilution.dilution_factor(DilutionMethod.BUILT, 0.30) == 0.0


class TestDaiquiri:
    """Daiquiri 60/30/20, shakerato."""

    def test_extensive_quantities(self, daiquiri: Recipe) -> None:
        profile = calculate_balance(daiquiri)

        assert profile.total_volume_ml == pytest.approx(110.0)
        # 60·0.40 = 24 ml di alcol puro
        assert profile.pure_alcohol_ml == pytest.approx(24.0)
        # 60·0.95 + 30·1.03 + 20·1.23 = 57 + 30.9 + 24.6
        assert profile.total_mass_g == pytest.approx(112.5)
        # 30·1.03·0.075 + 20·1.23·0.50 = 2.3175 + 12.3
        assert profile.sugar_mass_g == pytest.approx(14.6175, abs=1e-4)
        # 30·1.03·0.06
        assert profile.acid_mass_g == pytest.approx(1.854, abs=1e-4)

    def test_intensive_quantities_before_dilution(self, daiquiri: Recipe) -> None:
        profile = calculate_balance(daiquiri)

        assert profile.abv_pre == pytest.approx(24.0 / 110.0, abs=1e-6)
        assert profile.brix_pre == pytest.approx(14.6175 / 112.5 * 100, abs=1e-4)
        assert profile.acidity_pre == pytest.approx(1.854 / 112.5 * 100, abs=1e-4)

    def test_dilution_lowers_every_intensive_quantity(self, daiquiri: Recipe) -> None:
        profile = calculate_balance(daiquiri)

        assert profile.dilution_water_ml > 0
        assert profile.abv_post < profile.abv_pre
        assert profile.brix_post < profile.brix_pre
        assert profile.acidity_post < profile.acidity_pre

    def test_sugar_acid_ratio_is_invariant_under_dilution(self, daiquiri: Recipe) -> None:
        """L'acqua abbassa Brix e acidità nella stessa proporzione.

        È la proprietà che rende il rapporto l'indicatore stabile
        dell'equilibrio: non dipende da quanto si è shakerato.
        """
        profile = calculate_balance(daiquiri)
        assert profile.sugar_acid_ratio is not None
        post_ratio = profile.brix_post / profile.acidity_post
        assert profile.sugar_acid_ratio == pytest.approx(post_ratio, rel=1e-9)

    def test_sixty_thirty_twenty_lands_just_above_the_sour_window(self, daiquiri: Recipe) -> None:
        """Con sciroppo 1:1, il 60/30/20 è più dolce della finestra classica.

        Il rapporto vale 7.88 contro un limite superiore di 7.0. Non è un
        difetto del modello ma un suo risultato utile: il dosaggio
        "canonico" che gira nei manuali presuppone spesso uno sciroppo
        ricco 2:1, e con uno sciroppo 1:1 la stessa proporzione sposta il
        drink verso il dolce. È esattamente il tipo di scarto che il
        solver esiste per correggere.
        """
        profile = calculate_balance(daiquiri)
        assert profile.sugar_acid_ratio == pytest.approx(7.884, abs=1e-3)
        assert profile.sugar_acid_ratio > SOUR_RATIO_UPPER_BOUND
        assert profile.is_balanced_sour is False

    def test_reducing_the_syrup_brings_it_inside_the_window(
        self,
        white_rum: Ingredient,
        lime_juice: Ingredient,
        simple_syrup: Ingredient,
    ) -> None:
        """60/30/15 con sciroppo 1:1 cade dentro la finestra dei sour."""
        recipe = Recipe(
            id="daiquiri-dry",
            name="Daiquiri (dry)",
            dilution_method=DilutionMethod.SHAKEN,
            serving_ice=ServingIce.NONE,
            ingredients=(
                RecipeIngredient(ingredient=white_rum, volume_ml=60.0),
                RecipeIngredient(ingredient=lime_juice, volume_ml=30.0),
                RecipeIngredient(ingredient=simple_syrup, volume_ml=15.0),
            ),
        )
        profile = calculate_balance(recipe)

        assert profile.sugar_acid_ratio == pytest.approx(6.226, abs=1e-3)
        assert SOUR_RATIO_LOWER_BOUND <= profile.sugar_acid_ratio <= SOUR_RATIO_UPPER_BOUND
        assert profile.is_balanced_sour is True


class TestNegroni:
    """Negroni 30/30/30, mescolato — caso senza acidi significativi."""

    def test_stirred_profile_matches_hand_computation(self, negroni: Recipe) -> None:
        profile = calculate_balance(negroni)

        # (30·0.43 + 30·0.16 + 30·0.25) / 90 = 25.2/90
        assert profile.abv_pre == pytest.approx(0.28, abs=1e-9)
        assert profile.dilution_factor == pytest.approx(0.43784, abs=1e-5)
        assert profile.dilution_water_ml == pytest.approx(90 * 0.43784, abs=1e-4)
        assert profile.final_volume_ml == pytest.approx(90 + 39.4056, abs=1e-4)
        assert profile.abv_post == pytest.approx(25.2 / 129.4056, abs=1e-5)

    def test_abv_post_percent_is_the_label_value(self, negroni: Recipe) -> None:
        profile = calculate_balance(negroni)
        assert profile.abv_post_percent == pytest.approx(profile.abv_post * 100)
        assert 18.0 < profile.abv_post_percent < 21.0


class TestEdgeCases:
    def test_an_immeasurably_small_acidity_counts_as_none(self) -> None:
        """Caso trovato da Hypothesis, non immaginato a tavolino.

        Un'acidità denormale (10⁻³⁰⁹) non è zero, quindi superava la
        guardia `== 0` e faceva traboccare la divisione a infinito. Il
        valore si propagava silenzioso fino al profilo restituito: nessuna
        eccezione, solo un numero che non esiste. La soglia di rilevabilità
        lo tratta per quello che è — assenza di acido.
        """
        assert sugar_acid_ratio(brix=50.0, acidity=2.2e-309) is None
        assert sugar_acid_ratio(brix=50.0, acidity=0.0) is None
        # Appena sopra la soglia il rapporto torna a esistere.
        assert sugar_acid_ratio(brix=50.0, acidity=1e-6) == pytest.approx(5e7)

    def test_ratio_is_none_without_acids(
        self, white_rum: Ingredient, simple_syrup: Ingredient
    ) -> None:
        """Senza acidi il rapporto non è infinito: non esiste."""
        recipe = Recipe(
            id="zero-acidity",
            name="Rum & Syrup",
            dilution_method=DilutionMethod.STIRRED,
            serving_ice=ServingIce.NONE,
            ingredients=(
                RecipeIngredient(ingredient=white_rum, volume_ml=50.0),
                RecipeIngredient(ingredient=simple_syrup, volume_ml=10.0),
            ),
        )
        profile = calculate_balance(recipe)

        assert profile.acidity_pre == pytest.approx(0.0)
        assert profile.sugar_acid_ratio is None
        assert profile.is_balanced_sour is False

    def test_built_drink_is_served_undiluted(
        self, white_rum: Ingredient, lime_juice: Ingredient
    ) -> None:
        recipe = Recipe(
            id="built",
            name="Built Highball",
            dilution_method=DilutionMethod.BUILT,
            serving_ice=ServingIce.CUBES,
            ingredients=(
                RecipeIngredient(ingredient=white_rum, volume_ml=50.0),
                RecipeIngredient(ingredient=lime_juice, volume_ml=20.0),
            ),
        )
        profile = calculate_balance(recipe)

        assert profile.dilution_factor == pytest.approx(0.0)
        assert profile.dilution_water_ml == pytest.approx(0.0)
        assert profile.final_volume_ml == pytest.approx(profile.total_volume_ml)
        assert profile.abv_post == pytest.approx(profile.abv_pre)
        assert profile.brix_post == pytest.approx(profile.brix_pre)

    def test_alcohol_free_recipe_has_zero_abv_but_real_dilution(
        self, lime_juice: Ingredient, simple_syrup: Ingredient
    ) -> None:
        recipe = Recipe(
            id="no-alcohol",
            name="Lime Cordial Sour",
            dilution_method=DilutionMethod.SHAKEN,
            serving_ice=ServingIce.NONE,
            ingredients=(
                RecipeIngredient(ingredient=lime_juice, volume_ml=30.0),
                RecipeIngredient(ingredient=simple_syrup, volume_ml=20.0),
            ),
        )
        profile = calculate_balance(recipe)

        assert profile.abv_pre == 0.0
        assert profile.abv_post == 0.0
        assert profile.dilution_factor == pytest.approx(0.203)
        assert profile.dilution_water_ml == pytest.approx(50 * 0.203)

    def test_water_mass_is_added_to_the_denominator_of_post_quantities(
        self, daiquiri: Recipe
    ) -> None:
        """La massa finale include l'acqua di fusione a 1 g/ml.

        È la conversione più facile da sbagliare del modello: Brix e
        acidità sono rapporti di *massa*, mentre la diluizione è calcolata
        in *volume*.
        """
        profile = calculate_balance(daiquiri)
        assert profile.final_mass_g == pytest.approx(
            profile.total_mass_g + profile.dilution_water_ml
        )
        assert profile.brix_post == pytest.approx(profile.sugar_mass_g / profile.final_mass_g * 100)
