"""BalancingSolver — ottimizzazione vincolata dei volumi (SciPy SLSQP).

ADR-001: il solver calcola **quanto** di ciascun ingrediente, mai
**quali** ingredienti. La selezione è compito del matcher organolettico.
Questa separazione è la ragione per cui il problema resta ben posto: gli
ingredienti fissano le colonne della matrice, il solver cerca solo il
vettore dei volumi.

Formulazione
------------
Variabili:  x ∈ ℝⁿ, i volumi in ml (n = numero di ingredienti).

Minimizzare: la somma pesata degli errori **relativi** quadratici sui
target organolettici post-diluizione. L'errore relativo, e non assoluto,
è ciò che rende confrontabili grandezze di unità diverse: 0.01 di ABV e
1 °Bx non sono errori paragonabili in valore assoluto, lo sono in
percentuale del rispettivo target.

Soggetto a:
  * bounds  min_i ≤ x_i ≤ max_i   (per ingrediente)
  * vincolo di uguaglianza sul volume finale, quando richiesto;
  * tetto di disuguaglianza sul volume finale, se la ricetta dichiara un
    bicchiere con capienza nota (ADR-0009).

Il volume è un **vincolo** e non un obiettivo: una coppa da 90 ml ne
contiene 90, non "circa 90 con peso 0.5". Modellarlo come penalità
significherebbe accettare in silenzio un drink che trabocca o lascia il
bicchiere mezzo vuoto, in cambio di un ABV leggermente più preciso.

Perché SLSQP: il problema è non lineare (il fattore di diluizione è
quadratico in ABV, che a sua volta è un rapporto fra funzioni lineari di
x), vincolato, di dimensione piccola (n tipicamente 3-6) e con variabili
continue. SLSQP è il metodo di riferimento per questa classe: gestisce
nativamente bounds e vincoli di uguaglianza, e converge in poche decine
di iterazioni su problemi di questa taglia.
"""

from __future__ import annotations

import math
from typing import Any, Final

import numpy as np
from scipy.optimize import minimize

from app.domain.balance import BalanceProfile
from app.domain.entities import Recipe
from app.domain.services.balance_calculator import calculate_balance
from app.domain.services.glassware import recipe_volume_cap_ml

from .models import (
    SolverResult,
    SolverSettings,
    SolverStatus,
    TargetProfile,
    TargetResidual,
)

#: Scala minima nel denominatore degli errori relativi: evita la divisione
#: per zero quando un target è nullo, senza introdurre discontinuità.
_EPSILON: Final[float] = 1e-9

#: Scala di regolarizzazione del residuo sul rapporto zuccheri/acidi.
#: In grammi: sotto un milligrammo le due masse sono rumore di misura.
_RATIO_SCALE_FLOOR: Final[float] = 1e-3

#: Peso del termine di regolarizzazione di Tikhonov quando esistono
#: obiettivi organolettici: abbastanza piccolo da non spostare la
#: soluzione, abbastanza da rompere le degenerazioni. Fra due dosaggi che
#: servono i target ugualmente bene preferisce quello più vicino alla
#: ricetta di partenza, cioè all'intento di chi l'ha scritta.
_TIE_BREAK_REGULARIZATION_WEIGHT: Final[float] = 1e-6

#: Peso quando il solo target è il volume finale. In quel caso la
#: regolarizzazione **è** l'obiettivo — la soluzione cercata è il
#: riscalamento proporzionale — e lasciarla a 1e-6 la renderebbe
#: numericamente invisibile: le sue variazioni cadrebbero sotto `ftol` e
#: SLSQP si fermerebbe al primo punto ammissibile che incontra, cioè in un
#: punto qualsiasi della superficie del vincolo.
_PRIMARY_REGULARIZATION_WEIGHT: Final[float] = 1.0

#: Tolleranza sulla violazione del vincolo di volume, in frazione del
#: target: 0.1% di 90 ml è meno di un decimo di ml, sotto la risoluzione
#: di qualunque dosatore.
_FEASIBILITY_TOLERANCE: Final[float] = 1e-3


def _relative_squared_error(achieved: float, target: float) -> float:
    """((ottenuto − richiesto) / richiesto)², con denominatore protetto."""
    denominator = abs(target) if abs(target) > _EPSILON else _EPSILON
    return ((achieved - target) / denominator) ** 2


def _ratio_squared_error(sugar_mass_g: float, acid_mass_g: float, target_ratio: float) -> float:
    """Errore sul rapporto zuccheri/acidi, in forma **lineare e liscia**.

    Il rapporto zuccheri/acidi ha una singolarità in acido nullo, e
    valutarlo direttamente produce un obiettivo discontinuo: SLSQP stima
    il gradiente per differenze finite e su un salto non sa in che
    direzione muoversi.

    La riformulazione elimina la singolarità senza cambiare il problema.
    Imporre zuccheri/acidi = r equivale a imporre il residuo lineare
    zuccheri − r·acidi = 0 (in grammi), che è definito e derivabile
    ovunque, anche in acido nullo — dove anzi ha gradiente non nullo, e
    quindi spinge correttamente il solver ad aggiungere acido invece di
    fermarsi. Usa le masse e non il campo `sugar_acid_ratio` del profilo,
    perché quello vale `None` sotto la soglia di acidità percepibile,
    proprio dove il solver deve sapere in che direzione andare.

    Il denominatore è la norma euclidea dei due termini (con un pavimento
    che evita lo 0/0 sulla ricetta degenere senza zuccheri né acidi):
    rende l'errore adimensionale e confrontabile con gli altri, e limitato
    in [0, 2], quindi un solo target mal servito non può dominare la somma.
    """
    scaled_acid = target_ratio * acid_mass_g
    residual = sugar_mass_g - scaled_acid
    scale = math.sqrt(
        sugar_mass_g * sugar_mass_g + scaled_acid * scaled_acid + _RATIO_SCALE_FLOOR**2
    )
    return (residual / scale) ** 2


class BalancingSolver:
    """Calcola i volumi che avvicinano una ricetta ai target richiesti.

    Stateless e riutilizzabile: la configurazione sta in `SolverSettings`,
    passata al costruttore o sovrascritta per singola chiamata. Essendo
    puramente CPU-bound, va invocato fuori dall'event loop (ADR-002): i
    casi d'uso lo fanno con `asyncio.to_thread`.
    """

    def __init__(self, settings: SolverSettings | None = None) -> None:
        self._settings = settings or SolverSettings()

    # -- API pubblica -----------------------------------------------------

    def solve(
        self,
        recipe: Recipe,
        target: TargetProfile,
        settings: SolverSettings | None = None,
    ) -> SolverResult:
        """Risolve il problema e restituisce l'esito completo."""
        config = settings or self._settings
        per_ingredient = [config.bounds_for(item.ingredient.id) for item in recipe.ingredients]
        bounds = [(limits.min_ml, limits.max_ml) for limits in per_ingredient]
        lower = np.array([bound[0] for bound in bounds], dtype=float)
        upper = np.array([bound[1] for bound in bounds], dtype=float)

        start = np.clip(np.array(recipe.volumes_ml, dtype=float), lower, upper)
        anchor = self._proportional_anchor(recipe, target, start, lower, upper)

        constraints = self._build_constraints(recipe, target)

        best: np.ndarray | None = None
        best_objective = math.inf
        best_start_index = 0
        best_success = False
        best_iterations = 0
        best_message = ""
        hit_iteration_limit = False

        for index, x0 in enumerate(self._starting_points(start, lower, upper, config)):
            outcome = minimize(
                self._objective,
                x0=x0,
                args=(recipe, target, config, anchor),
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"maxiter": config.max_iterations, "ftol": config.tolerance},
            )
            if getattr(outcome, "status", None) == 9:
                hit_iteration_limit = True

            candidate = np.clip(np.asarray(outcome.x, dtype=float), lower, upper)
            if not np.all(np.isfinite(candidate)):
                continue

            # Il confronto fra ripartenze usa una penalità di infattibilità,
            # non il solo valore dell'obiettivo: una soluzione che viola il
            # vincolo di volume non è "migliore" per quanto bene serva i
            # target organolettici.
            score = self._objective(candidate, recipe, target, config, anchor)
            score += self._constraint_violation(candidate, recipe, target) * 1e3

            if score < best_objective:
                best_objective = score
                best = candidate
                best_start_index = index
                best_success = bool(outcome.success)
                best_iterations = int(getattr(outcome, "nit", 0))
                best_message = str(getattr(outcome, "message", ""))

        if best is None:
            return self._failure_result(recipe, target, config)

        # L'ammissibilità si valuta sulla soluzione **continua**: INFEASIBLE
        # deve significare "il problema come posto non ha soluzione entro i
        # bounds", che è una proprietà del problema. Lo scarto introdotto
        # dopo, arrotondando al passo del dosatore, è una quantizzazione
        # attesa e non un fallimento del solver — giudicarla con la stessa
        # tolleranza marcherebbe come irrisolvibili problemi risolti bene.
        violation = self._constraint_violation(best, recipe, target)
        status = self._classify(best_success, hit_iteration_limit, violation)
        message = best_message or status.value
        if status is SolverStatus.INFEASIBLE and self._glass_cap_ml(recipe) is not None:
            message = (
                f"{message}; the glass holds at most {self._glass_cap_ml(recipe):.1f} ml "
                "of drink"
            )

        rounded = self._round_to_step(best, lower, upper, config.rounding_step_ml)
        final_recipe = recipe.with_volumes(tuple(rounded.tolist()))
        profile = calculate_balance(final_recipe)

        return SolverResult(
            status=status,
            recipe=final_recipe,
            profile=profile,
            objective_value=self._objective(rounded, recipe, target, config, anchor),
            iterations=best_iterations,
            residuals=self._residuals(profile, target),
            message=message,
            winning_start=best_start_index,
        )

    # -- Funzione obiettivo ----------------------------------------------

    def _objective(
        self,
        volumes: np.ndarray,
        recipe: Recipe,
        target: TargetProfile,
        config: SolverSettings,
        anchor: np.ndarray,
    ) -> float:
        # Rete di sicurezza: le entità di dominio rifiutano volumi non
        # positivi, e le differenze finite di SLSQP possono sfiorare il
        # bordo inferiore. Non altera l'ottimo, che sta dentro i bounds.
        safe = np.maximum(np.asarray(volumes, dtype=float), _EPSILON)
        profile = calculate_balance(recipe.with_volumes(tuple(safe.tolist())))
        weights = config.weights

        total = 0.0
        if target.abv is not None:
            total += weights.abv * _relative_squared_error(profile.abv_post, target.abv)
        if target.brix is not None:
            total += weights.brix * _relative_squared_error(profile.brix_post, target.brix)
        if target.acidity is not None:
            total += weights.acidity * _relative_squared_error(profile.acidity_post, target.acidity)
        if target.sugar_acid_ratio is not None:
            total += weights.sugar_acid_ratio * _ratio_squared_error(
                profile.sugar_mass_g, profile.acid_mass_g, target.sugar_acid_ratio
            )

        # Regolarizzazione: scarto quadratico relativo dalle proporzioni
        # originali della ricetta.
        regularization = (
            _TIE_BREAK_REGULARIZATION_WEIGHT
            if target.has_objectives
            else _PRIMARY_REGULARIZATION_WEIGHT
        )
        deviation = (safe - anchor) / np.maximum(anchor, _EPSILON)
        total += regularization * float(np.sum(deviation * deviation))

        return total

    # -- Vincoli ----------------------------------------------------------

    @staticmethod
    def _glass_cap_ml(recipe: Recipe) -> float | None:
        """Tetto al volume del drink imposto dal bicchiere, se ne ha uno."""
        return recipe_volume_cap_ml(recipe)

    def _build_constraints(
        self, recipe: Recipe, target: TargetProfile
    ) -> tuple[dict[str, Any], ...]:
        constraints: list[dict[str, Any]] = []

        def final_volume(volumes: np.ndarray) -> float:
            safe = np.maximum(np.asarray(volumes, dtype=float), _EPSILON)
            return calculate_balance(recipe.with_volumes(tuple(safe.tolist()))).final_volume_ml

        if target.final_volume_ml is not None:
            wanted = target.final_volume_ml

            def volume_residual(volumes: np.ndarray) -> float:
                # Normalizzato sul target: mantiene il vincolo nello stesso
                # ordine di grandezza dell'obiettivo, che è ciò che SLSQP si
                # aspetta per calcolare moltiplicatori di Lagrange sensati.
                return (final_volume(volumes) - wanted) / wanted

            constraints.append({"type": "eq", "fun": volume_residual})

        cap = self._glass_cap_ml(recipe)
        if cap is not None:

            def capacity_slack(volumes: np.ndarray) -> float:
                # SLSQP vuole `fun >= 0`: il margine residuo del bicchiere,
                # normalizzato come sopra.
                return (cap - final_volume(volumes)) / cap

            constraints.append({"type": "ineq", "fun": capacity_slack})

        return tuple(constraints)

    def _constraint_violation(
        self, volumes: np.ndarray, recipe: Recipe, target: TargetProfile
    ) -> float:
        cap = self._glass_cap_ml(recipe)
        if target.final_volume_ml is None and cap is None:
            return 0.0
        profile = calculate_balance(recipe.with_volumes(tuple(volumes.tolist())))
        final_volume = profile.final_volume_ml
        violation = 0.0
        if target.final_volume_ml is not None:
            violation += abs(final_volume - target.final_volume_ml) / target.final_volume_ml
        if cap is not None:
            # Il tetto si viola solo da un lato: stare sotto non costa nulla.
            violation += max(0.0, final_volume - cap) / cap
        return violation

    # -- Punti di partenza -------------------------------------------------

    def _proportional_anchor(
        self,
        recipe: Recipe,
        target: TargetProfile,
        start: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
    ) -> np.ndarray:
        """La ricetta di partenza riscalata al volume richiesto.

        Riscalare tutti i volumi dello stesso fattore lascia invariato
        l'ABV pre-diluizione, quindi anche il fattore di diluizione: il
        volume finale scala esattamente in modo lineare. L'ancora è perciò
        la soluzione *esatta* del problema di solo volume, ed è il punto
        naturale attorno a cui regolarizzare quando ci sono anche obiettivi
        organolettici.
        """
        if target.final_volume_ml is None:
            floored: np.ndarray = np.maximum(start, _EPSILON)
            return floored
        current = calculate_balance(recipe.with_volumes(tuple(start.tolist()))).final_volume_ml
        if current <= 0:
            fallback: np.ndarray = np.maximum(start, _EPSILON)
            return fallback
        scale = target.final_volume_ml / current
        scaled: np.ndarray = np.clip(start * scale, lower, upper)
        return scaled

    def _starting_points(
        self,
        start: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
        config: SolverSettings,
    ) -> list[np.ndarray]:
        """Ricetta di partenza più N punti pseudo-casuali riproducibili."""
        points = [start]
        if config.restarts == 0:
            return points
        rng = np.random.default_rng(config.random_seed)
        for _ in range(config.restarts):
            points.append(rng.uniform(lower, upper))
        return points

    # -- Post-processing ---------------------------------------------------

    @staticmethod
    def _round_to_step(
        volumes: np.ndarray, lower: np.ndarray, upper: np.ndarray, step: float
    ) -> np.ndarray:
        """Arrotonda al passo del dosatore, restando dentro i bounds."""
        rounded: np.ndarray = np.clip(np.round(volumes / step) * step, lower, upper)
        return rounded

    @staticmethod
    def _classify(success: bool, hit_iteration_limit: bool, violation: float) -> SolverStatus:
        if violation > _FEASIBILITY_TOLERANCE:
            return SolverStatus.INFEASIBLE
        if success:
            return SolverStatus.CONVERGED
        if hit_iteration_limit:
            return SolverStatus.MAX_ITERATIONS
        return SolverStatus.FAILED

    @staticmethod
    def _residuals(profile: BalanceProfile, target: TargetProfile) -> tuple[TargetResidual, ...]:
        residuals: list[TargetResidual] = []
        if target.abv is not None:
            residuals.append(TargetResidual("abv", target.abv, profile.abv_post))
        if target.brix is not None:
            residuals.append(TargetResidual("brix", target.brix, profile.brix_post))
        if target.acidity is not None:
            residuals.append(TargetResidual("acidity", target.acidity, profile.acidity_post))
        if target.sugar_acid_ratio is not None:
            residuals.append(
                TargetResidual(
                    "sugar_acid_ratio", target.sugar_acid_ratio, profile.sugar_acid_ratio
                )
            )
        if target.final_volume_ml is not None:
            residuals.append(
                TargetResidual("final_volume_ml", target.final_volume_ml, profile.final_volume_ml)
            )
        return tuple(residuals)

    def _failure_result(
        self, recipe: Recipe, target: TargetProfile, config: SolverSettings
    ) -> SolverResult:
        """Nessuna ripartenza ha prodotto un punto finito: si torna all'input.

        Restituire la ricetta originale con stato `FAILED` è preferibile a
        sollevare un'eccezione: il chiamante ha comunque qualcosa di valido
        da mostrare, e sa che non è ottimizzato.
        """
        profile = calculate_balance(recipe)
        return SolverResult(
            status=SolverStatus.FAILED,
            recipe=recipe,
            profile=profile,
            objective_value=math.inf,
            iterations=0,
            residuals=self._residuals(profile, target),
            message="solver produced no finite solution; returning the original recipe",
        )
