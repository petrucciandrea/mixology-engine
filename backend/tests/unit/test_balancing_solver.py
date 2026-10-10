"""Il solver SLSQP: convergenza, vincoli, diagnostica.

Diversi test qui sotto coprono difetti concreti emersi dall'audit della
prima versione: l'esito della minimizzazione scartato, la penalità
costante sul rapporto zuccheri/acidi che azzerava i gradienti, il volume
finale trattato come obiettivo pesato invece che come vincolo, e
l'arrotondamento applicato senza ricalcolare il profilo.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.application.solver.balancing_solver import BalancingSolver
from app.application.solver.models import (
    SolverSettings,
    SolverStatus,
    TargetProfile,
    TargetWeights,
    VolumeBounds,
)
from app.domain.entities import Ingredient, Recipe, RecipeIngredient
from app.domain.enums import DilutionMethod, GlassType, ServingIce
from app.domain.errors import SolverError
from app.domain.services.balance_calculator import calculate_balance
from app.domain.services.glassware import recipe_volume_cap_ml


@pytest.fixture
def solver() -> BalancingSolver:
    return BalancingSolver()


class TestConvergence:
    def test_moves_an_unbalanced_daiquiri_onto_its_targets(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        before = calculate_balance(unbalanced_daiquiri)
        # Tre target **compatibili fra loro**: sono i valori di un Daiquiri
        # 60/25/20 (15.0 %, 7.85 °Bx, 0.94 % p/v). Con tre ingredienti e il
        # volume libero i target non sono indipendenti: 16 % / 10 °Bx / 1.0 %
        # non descrivono nessuna ricetta di rum, lime e sciroppo, e il solver
        # (giustamente) non li raggiunge tutti.
        target = TargetProfile(abv=0.15, brix=8.0, acidity=0.95)

        result = solver.solve(unbalanced_daiquiri, target)
        after = result.profile

        assert result.status is SolverStatus.CONVERGED
        # Ogni target migliora rispetto al punto di partenza...
        assert abs(after.abv_post - 0.15) < abs(before.abv_post - 0.15)
        assert abs(after.brix_post - 8.0) < abs(before.brix_post - 8.0)
        assert abs(after.acidity_post - 0.95) < abs(before.acidity_post - 0.95)
        # ...e l'errore residuo è entro la tolleranza di un bar, non solo
        # "minore di prima".
        assert result.max_relative_error is not None
        assert result.max_relative_error < 0.10

    def test_reports_the_residual_of_every_requested_target(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        target = TargetProfile(abv=0.16, brix=10.0, final_volume_ml=150.0)
        result = solver.solve(unbalanced_daiquiri, target)

        assert {residual.name for residual in result.residuals} == {
            "abv",
            "brix",
            "final_volume_ml",
        }
        for residual in result.residuals:
            assert residual.achieved is not None
            assert residual.relative_error is not None

    def test_is_deterministic(self, solver: BalancingSolver, unbalanced_daiquiri: Recipe) -> None:
        """Stesso input, stesso output — anche con il multi-start attivo.

        Il seme del generatore è fissato nelle impostazioni proprio per
        questo: un solver non riproducibile rende i test intermittenti e i
        risultati impossibili da discutere.
        """
        target = TargetProfile(abv=0.16, brix=10.0, acidity=1.0)
        first = solver.solve(unbalanced_daiquiri, target)
        second = solver.solve(unbalanced_daiquiri, target)

        assert first.recipe.volumes_ml == second.recipe.volumes_ml
        assert first.objective_value == pytest.approx(second.objective_value)


class TestVolumeConstraint:
    def test_final_volume_is_honoured_as_a_hard_constraint(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        """Una coppa da 150 ml ne contiene 150, non "circa 150".

        Nella prima versione il volume era una penalità pesata 0.5 nella
        funzione obiettivo, e il solver poteva scambiarlo volentieri per
        un ABV leggermente più preciso.
        """
        target = TargetProfile(abv=0.16, brix=9.0, final_volume_ml=150.0)
        result = solver.solve(unbalanced_daiquiri, target)

        assert result.status is SolverStatus.CONVERGED
        # Tolleranza di mezzo ml: il passo di arrotondamento del dosatore.
        assert result.profile.final_volume_ml == pytest.approx(150.0, abs=0.5)

    def test_a_volume_only_target_rescales_the_recipe_proportionally(
        self, solver: BalancingSolver, daiquiri: Recipe
    ) -> None:
        """Senza obiettivi organolettici la soluzione esatta è il riscalamento.

        È la proprietà che il termine di regolarizzazione garantisce: fra
        le infinite combinazioni di volumi che danno quel volume finale,
        il solver sceglie quella che conserva le proporzioni dell'autore.
        """
        original = calculate_balance(daiquiri)
        wanted = original.final_volume_ml * 0.8

        result = solver.solve(daiquiri, TargetProfile(final_volume_ml=wanted))

        assert result.profile.final_volume_ml == pytest.approx(wanted, abs=0.5)
        assert result.profile.abv_pre == pytest.approx(original.abv_pre, abs=1e-3)
        assert result.profile.brix_pre == pytest.approx(original.brix_pre, abs=1e-2)

    def test_reports_infeasible_when_the_bounds_cannot_reach_the_volume(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        """Tre ingredienti da al massimo 10 ml non riempiono un tiki mug.

        Il punto non è che il solver fallisca, è che lo dica: senza uno
        stato esplicito il chiamante riceverebbe una ricetta plausibile e
        sbagliata.
        """
        settings = SolverSettings(default_bounds=VolumeBounds(min_ml=5.0, max_ml=10.0))
        target = TargetProfile(final_volume_ml=500.0)

        result = solver.solve(unbalanced_daiquiri, target, settings)

        assert result.status is SolverStatus.INFEASIBLE
        assert result.status.is_usable is False


class TestBounds:
    def test_respects_the_default_bounds(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        settings = SolverSettings(default_bounds=VolumeBounds(min_ml=10.0, max_ml=40.0))
        result = solver.solve(
            unbalanced_daiquiri, TargetProfile(abv=0.30, brix=4.0, acidity=2.0), settings
        )

        assert all(10.0 <= volume <= 40.0 for volume in result.recipe.volumes_ml)

    def test_respects_per_ingredient_bounds(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        """ "Il rum non scende sotto i 50 ml" è una scelta d'autore.

        Senza bounds per ingrediente l'unico modo di ottenerla sarebbe
        scartare a mano i risultati del solver.
        """
        settings = SolverSettings(
            bounds_by_ingredient={"rum": VolumeBounds(min_ml=50.0, max_ml=55.0)}
        )
        result = solver.solve(
            unbalanced_daiquiri, TargetProfile(abv=0.12, brix=8.0, acidity=1.2), settings
        )

        rum_volume = next(
            item.volume_ml for item in result.recipe.ingredients if item.ingredient.id == "rum"
        )
        assert 50.0 <= rum_volume <= 55.0


class TestSugarAcidRatioTarget:
    def test_reaches_a_ratio_target(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        result = solver.solve(unbalanced_daiquiri, TargetProfile(sugar_acid_ratio=6.0))

        assert result.status is SolverStatus.CONVERGED
        assert result.profile.sugar_acid_ratio is not None
        assert result.profile.sugar_acid_ratio == pytest.approx(6.0, abs=0.15)

    def test_adds_acidity_to_a_recipe_that_has_none(
        self,
        solver: BalancingSolver,
        white_rum: Ingredient,
        lime_juice: Ingredient,
        simple_syrup: Ingredient,
    ) -> None:
        """Il caso che rompeva la versione precedente del solver.

        Con acidità nulla il rapporto è `None`, e l'obiettivo restituiva la
        costante 1e6: un plateau su cui le differenze finite di SLSQP
        misurano gradiente zero, quindi il solver non sapeva in che
        direzione muoversi e restava fermo. La riformulazione lineare
        (zuccheri − r·acidi, in grammi) è derivabile anche lì, e spinge ad
        aggiungere acido.
        """
        recipe = Recipe(
            id="no-acid",
            name="Rum, Syrup and a Splash of Lime",
            dilution_method=DilutionMethod.SHAKEN,
            serving_ice=ServingIce.NONE,
            ingredients=(
                RecipeIngredient(ingredient=white_rum, volume_ml=60.0),
                RecipeIngredient(ingredient=simple_syrup, volume_ml=30.0),
                # Dose minima di lime: acidità quasi nulla, ma il solver può
                # aumentarla. Con la vecchia penalità costante restava qui.
                RecipeIngredient(ingredient=lime_juice, volume_ml=5.0),
            ),
        )
        before = calculate_balance(recipe)
        # 5 ml di lime = 0.3 g di acido su 95 ml: 0.32 % p/v, sotto la soglia
        # percepibile, quindi il rapporto del profilo non esiste. Il punto di
        # partenza si misura sulle masse: 18.5 g di zuccheri / 0.3 g ≈ 62.
        assert before.sugar_acid_ratio is None
        assert (
            before.sugar_mass_g / before.acid_mass_g > 20.0
        ), "il punto di partenza è molto sbilanciato"

        result = solver.solve(recipe, TargetProfile(sugar_acid_ratio=6.0))

        assert result.profile.sugar_acid_ratio is not None
        assert result.profile.sugar_acid_ratio == pytest.approx(6.0, abs=0.3)


class TestRoundingAndReporting:
    def test_volumes_are_rounded_to_the_jigger_step(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        settings = SolverSettings(rounding_step_ml=0.5)
        result = solver.solve(unbalanced_daiquiri, TargetProfile(abv=0.16, brix=10.0), settings)

        for volume in result.recipe.volumes_ml:
            assert volume * 2 == pytest.approx(round(volume * 2)), f"{volume} non è multiplo di 0.5"

    def test_the_reported_profile_belongs_to_the_returned_recipe(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        """Ciò che l'API dichiara è ciò che si ottiene versando.

        Prima l'arrotondamento avveniva dopo l'ottimizzazione e il profilo
        restituito era quello dei volumi in virgola mobile: numeri
        leggermente diversi da quelli effettivamente serviti.
        """
        result = solver.solve(unbalanced_daiquiri, TargetProfile(abv=0.16, brix=10.0))
        recomputed = calculate_balance(result.recipe)

        assert result.profile == recomputed

    def test_carries_the_iteration_count_and_a_message(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        result = solver.solve(unbalanced_daiquiri, TargetProfile(abv=0.16))

        assert result.iterations > 0
        assert result.message


class TestWeights:
    def test_a_zero_weight_removes_a_target_from_the_objective(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        """I pesi sono una leva reale, non una costante implicita.

        Azzerare il peso del Brix non rende l'ABV più preciso — con un solo
        obiettivo attivo la soluzione non è unica e a decidere è la
        regolarizzazione — ma smette di inseguire il Brix, che infatti si
        allontana dal suo target. È questo il comportamento da verificare.
        """
        target = TargetProfile(abv=0.16, brix=10.0)

        both = solver.solve(unbalanced_daiquiri, target)
        abv_only = solver.solve(
            unbalanced_daiquiri,
            target,
            SolverSettings(weights=TargetWeights(abv=1.0, brix=0.0)),
        )

        assert abs(abv_only.profile.brix_post - 10.0) > abs(both.profile.brix_post - 10.0)
        # L'obiettivo rimasto continua a essere servito bene.
        assert abv_only.profile.abv_post == pytest.approx(0.16, abs=0.005)


class TestInputValidation:
    def test_rejects_an_empty_target(self) -> None:
        with pytest.raises(SolverError, match="at least one target"):
            TargetProfile()

    def test_rejects_an_abv_expressed_as_a_percentage(self) -> None:
        """16 invece di 0.16 è l'errore più probabile su questo campo."""
        with pytest.raises(SolverError, match="fraction"):
            TargetProfile(abv=16.0)

    def test_rejects_inverted_bounds(self) -> None:
        with pytest.raises(SolverError):
            VolumeBounds(min_ml=50.0, max_ml=10.0)

    def test_rejects_a_non_positive_minimum(self) -> None:
        """Un minimo di zero permetterebbe al solver di eliminare un
        ingrediente, cioè di cambiare la ricetta invece di bilanciarla."""
        with pytest.raises(SolverError):
            VolumeBounds(min_ml=0.0)


class TestGlassCapacity:
    """La capienza del bicchiere è un vincolo di disuguaglianza (ADR-0009).

    A differenza del volume finale richiesto, che è un'uguaglianza, la
    capienza è un tetto: sotto di esso il solver è libero.
    """

    def test_a_recipe_without_a_glass_is_not_capped(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        result = solver.solve(unbalanced_daiquiri, TargetProfile(final_volume_ml=300.0))

        assert result.status.is_usable
        assert result.profile.final_volume_ml == pytest.approx(300.0, rel=0.01)

    def test_the_final_volume_is_capped_at_the_glass_capacity(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        """Il punto di partenza (~140 ml) non entra in un bicchierino da 50 ml:
        il solver, che da solo non avrebbe motivo di scendere, ci deve entrare."""
        glass = replace(unbalanced_daiquiri, glass=GlassType.SHOT)
        limit = recipe_volume_cap_ml(glass)
        assert limit is not None
        assert calculate_balance(glass).final_volume_ml > limit, "il test presuppone l'overflow"

        result = solver.solve(glass, TargetProfile(abv=0.16))

        assert result.status.is_usable
        assert result.profile.final_volume_ml <= limit * 1.01

    def test_the_cap_does_not_block_a_drink_that_already_fits(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        coupe = replace(unbalanced_daiquiri, glass=GlassType.COUPE)
        capped = solver.solve(coupe, TargetProfile(abv=0.16, brix=10.0))
        free = solver.solve(unbalanced_daiquiri, TargetProfile(abv=0.16, brix=10.0))

        assert capped.status is SolverStatus.CONVERGED
        assert capped.profile.final_volume_ml < 180.0, "il tetto non è attivo"
        # Con due target e tre incognite la soluzione non è unica e SLSQP può
        # scegliere un punto diverso sulla stessa valle: non si confrontano
        # i volumi, si verifica che i target siano serviti bene come prima.
        assert capped.max_relative_error is not None
        assert free.max_relative_error is not None
        assert capped.max_relative_error < 0.10

    def test_a_target_volume_above_the_capacity_is_infeasible(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        """220 ml non entrano in una coppa da 200 ml (utili: 180 ml)."""
        coupe = replace(unbalanced_daiquiri, glass=GlassType.COUPE)

        result = solver.solve(coupe, TargetProfile(final_volume_ml=220.0))

        assert result.status is SolverStatus.INFEASIBLE

    def test_a_target_volume_below_the_capacity_is_still_met(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        coupe = replace(unbalanced_daiquiri, glass=GlassType.COUPE)

        result = solver.solve(coupe, TargetProfile(final_volume_ml=120.0))

        assert result.status.is_usable
        assert result.profile.final_volume_ml == pytest.approx(120.0, rel=0.01)

    def test_serving_ice_lowers_the_cap(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        """Lo stesso bicchiere, ma con ghiaccio, ospita meno drink."""
        on_ice = replace(
            unbalanced_daiquiri, glass=GlassType.HIGHBALL, serving_ice=ServingIce.CUBES
        )

        # 360 ml × 0.9 × 0.65 = 210.6 ml: 230 ml non ci stanno, 180 sì (e
        # senza ghiaccio 230 ml ci starebbero, nei 324 ml utili).
        assert solver.solve(on_ice, TargetProfile(final_volume_ml=230.0)).status is (
            SolverStatus.INFEASIBLE
        )
        assert solver.solve(on_ice, TargetProfile(final_volume_ml=180.0)).status.is_usable
        neat = replace(on_ice, serving_ice=ServingIce.NONE)
        assert solver.solve(neat, TargetProfile(final_volume_ml=230.0)).status.is_usable

    def test_a_glass_without_capacity_does_not_constrain(
        self, solver: BalancingSolver, unbalanced_daiquiri: Recipe
    ) -> None:
        other = replace(unbalanced_daiquiri, glass=GlassType.OTHER)

        result = solver.solve(other, TargetProfile(final_volume_ml=300.0))

        assert result.status.is_usable
