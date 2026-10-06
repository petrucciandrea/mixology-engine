"""Verifica delle formule di bilanciamento e diluizione.

I valori attesi sono calcolati a mano dalle formule del domain model, non
copiati da un'esecuzione del codice: un test che si limita a fotografare
l'output conferma solo che il codice non è cambiato, non che è corretto.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.domain.balance import SUGAR_ACID_MIN_ACIDITY
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
        # 30·1.03·0.017 + 20·1.23·0.50 = 0.5253 + 12.3
        assert profile.sugar_mass_g == pytest.approx(12.8253, abs=1e-4)
        # L'acidità è % p/v: 6 g ogni 100 ml di lime, quindi 30·0.06 = 1.8 g.
        # La densità non entra: il dato è già per volume.
        assert profile.acid_mass_g == pytest.approx(1.8, abs=1e-9)

    def test_intensive_quantities_before_dilution(self, daiquiri: Recipe) -> None:
        profile = calculate_balance(daiquiri)

        assert profile.abv_pre == pytest.approx(24.0 / 110.0, abs=1e-6)
        # Il Brix è % peso: zuccheri / massa.
        assert profile.brix_pre == pytest.approx(12.8253 / 112.5 * 100, abs=1e-4)
        # L'acidità è % p/v: acidi / volume. 1.8 g su 110 ml.
        assert profile.acidity_pre == pytest.approx(1.8 / 110.0 * 100, abs=1e-9)

    def test_acidity_is_weight_per_volume_before_and_after_dilution(self, daiquiri: Recipe) -> None:
        """La dichiarazione "% w/v" deve valere anche per il valore calcolato.

        Gli ingredienti portano l'acidità in g/100 ml; se il risultato fosse
        g/g, `acidity_post` non sarebbe confrontabile con il dato di
        partenza né con l'etichetta mostrata all'utente. L'acqua di fusione
        entra nel denominatore come volume, e la massa d'acido si conserva.
        """
        profile = calculate_balance(daiquiri)

        assert profile.acidity_post == pytest.approx(
            profile.acid_mass_g / profile.final_volume_ml * 100.0
        )
        assert profile.acidity_post * profile.final_volume_ml / 100.0 == pytest.approx(
            profile.acid_mass_g
        )

    def test_dilution_lowers_every_intensive_quantity(self, daiquiri: Recipe) -> None:
        profile = calculate_balance(daiquiri)

        assert profile.dilution_water_ml > 0
        assert profile.abv_post < profile.abv_pre
        assert profile.brix_post < profile.brix_pre
        assert profile.acidity_post < profile.acidity_pre

    def test_sugar_acid_ratio_is_the_ratio_of_the_two_masses(self, daiquiri: Recipe) -> None:
        """Zuccheri e acidi in grammi: nessuna unità di concentrazione di mezzo.

        Brix è % peso e acidità è % p/v, quindi il loro quoziente
        mescolerebbe due basi diverse. Il rapporto fra le masse è
        adimensionale e dice la stessa cosa: quanti grammi di zucchero
        bilanciano un grammo di acido.
        """
        profile = calculate_balance(daiquiri)
        # 12.8253 g di zuccheri / 1.8 g di acidi
        assert profile.sugar_acid_ratio == pytest.approx(12.8253 / 1.8, abs=1e-4)

    def test_sugar_acid_ratio_does_not_depend_on_the_dilution(self, daiquiri: Recipe) -> None:
        """L'acqua abbassa zuccheri e acidi nella stessa proporzione.

        È la proprietà che rende il rapporto l'indicatore stabile
        dell'equilibrio: non dipende da quanto si è shakerato, né dal
        metodo. Si verifica cambiando la tecnica sulla stessa dose.
        """
        shaken = calculate_balance(daiquiri)
        built = calculate_balance(replace(daiquiri, dilution_method=DilutionMethod.BUILT))

        assert shaken.dilution_water_ml > built.dilution_water_ml == 0.0
        assert shaken.sugar_acid_ratio == pytest.approx(built.sugar_acid_ratio)

    def test_reducing_the_syrup_lowers_the_ratio(
        self,
        white_rum: Ingredient,
        lime_juice: Ingredient,
        simple_syrup: Ingredient,
    ) -> None:
        """60/30/15: meno sciroppo, meno zuccheri a parità di acidi."""
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

        # (30·1.03·0.017 + 15·1.23·0.50) / (30·0.06) = (0.5253 + 9.225) / 1.8
        assert profile.sugar_acid_ratio == pytest.approx(9.7503 / 1.8, abs=1e-4)


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

    def test_trace_acids_do_not_make_a_sugar_acid_ratio(self, negroni: Recipe) -> None:
        """Il Negroni non è "44 volte più dolce che acido": non è un sour.

        Vermouth e Campari portano 0.15 + 0.12 = 0.27 g di acidi su 90 ml,
        cioè 0.30 % p/v, sotto la soglia oltre la quale il drink ha un
        carattere acido. Il quoziente grezzo (12.7 g di zuccheri / 0.29 g)
        valeva 44 e la finestra dei sour lo leggeva come "stucchevole".
        """
        profile = calculate_balance(negroni)

        # 30·0.005 + 30·0.004 = 0.27 g su 90 ml
        assert profile.acid_mass_g == pytest.approx(0.27, abs=1e-9)
        assert profile.acidity_pre == pytest.approx(0.27 / 90.0 * 100, abs=1e-9)
        assert profile.acidity_pre < SUGAR_ACID_MIN_ACIDITY
        assert profile.sugar_acid_ratio is None


class TestGinTonic:
    def test_tonic_sugar_over_trace_acid_is_not_a_ratio(self, gin_tonic: Recipe) -> None:
        """Il caso dell'85: zuccheri veri della tonica, acido quasi assente.

        150 ml di tonica a 8.5 °Bx portano 13.1 g di zuccheri; 0.1 % di
        acidità sono 0.15 g su 200 ml (0.075 % p/v). Zuccheri e acidi sono
        corretti, è il loro quoziente (85) a non voler dire nulla.
        """
        profile = calculate_balance(gin_tonic)

        # 150·1.03·0.085 = 13.1325 g; 150·0.001 = 0.15 g
        assert profile.sugar_mass_g == pytest.approx(13.1325, abs=1e-4)
        assert profile.acid_mass_g == pytest.approx(0.15, abs=1e-9)
        assert profile.sugar_acid_ratio is None


class TestSugarAcidRatioFunction:
    def test_ratio_exists_only_above_the_perceptible_acidity(self) -> None:
        below = SUGAR_ACID_MIN_ACIDITY * 0.99
        at = SUGAR_ACID_MIN_ACIDITY

        assert sugar_acid_ratio(sugar_mass_g=12.0, acid_mass_g=1.0, acidity_pre=below) is None
        assert sugar_acid_ratio(sugar_mass_g=12.0, acid_mass_g=1.0, acidity_pre=at) == (
            pytest.approx(12.0)
        )


class TestEdgeCases:
    def test_an_immeasurably_small_acidity_counts_as_none(self) -> None:
        """Caso trovato da Hypothesis, non immaginato a tavolino.

        Un'acidità denormale (10⁻³⁰⁹) non è zero, quindi superava la
        guardia `== 0` e faceva traboccare la divisione a infinito. Il
        valore si propagava silenzioso fino al profilo restituito: nessuna
        eccezione, solo un numero che non esiste. Ora la soglia di
        acidità percepibile lo scarta a monte: un'acidità che non si
        misura non produce un rapporto, tantomeno infinito.
        """
        assert sugar_acid_ratio(sugar_mass_g=50.0, acid_mass_g=2.2e-309, acidity_pre=0.0) is None
        assert sugar_acid_ratio(sugar_mass_g=50.0, acid_mass_g=0.0, acidity_pre=0.0) is None

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

        È la conversione più facile da sbagliare del modello: il Brix è un
        rapporto di *massa*, mentre la diluizione è calcolata in *volume*
        (l'acidità, che è per volume, usa invece il volume finale).
        """
        profile = calculate_balance(daiquiri)
        assert profile.final_mass_g == pytest.approx(
            profile.total_mass_g + profile.dilution_water_ml
        )
        assert profile.brix_post == pytest.approx(profile.sugar_mass_g / profile.final_mass_g * 100)
