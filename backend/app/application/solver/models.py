"""Tipi del problema di ottimizzazione: input, configurazione, esito.

Sono dataclass della libreria standard, come nel dominio: il layer
applicativo resta indipendente dal framework web. SciPy compare solo
nell'implementazione del solver, non nel suo contratto — così un domani
si può sostituire SLSQP con un altro metodo senza toccare né i casi
d'uso né l'API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Final

from app.domain.balance import BalanceProfile
from app.domain.entities import Recipe
from app.domain.errors import SolverError

#: Volumi ammessi di default per un singolo ingrediente, in ml.
#: Il minimo non è zero: un solver libero di azzerare un ingrediente
#: risolverebbe il problema *eliminandolo*, cioè cambiando la ricetta
#: invece di bilanciarla. La selezione degli ingredienti è compito del
#: matcher, non del solver (ADR-001).
DEFAULT_MIN_VOLUME_ML: Final[float] = 5.0
DEFAULT_MAX_VOLUME_ML: Final[float] = 120.0


@dataclass(frozen=True, slots=True)
class VolumeBounds:
    """Intervallo di volume ammesso per un ingrediente."""

    min_ml: float = DEFAULT_MIN_VOLUME_ML
    max_ml: float = DEFAULT_MAX_VOLUME_ML

    def __post_init__(self) -> None:
        if self.min_ml <= 0:
            raise SolverError(f"min_ml must be greater than 0, got {self.min_ml}")
        if self.max_ml < self.min_ml:
            raise SolverError(
                f"max_ml ({self.max_ml}) must be greater than or equal to "
                f"min_ml ({self.min_ml})"
            )


@dataclass(frozen=True, slots=True)
class TargetWeights:
    """Peso relativo di ciascun obiettivo nella funzione costo.

    Esplicitare i pesi è metà del valore del solver: senza, la funzione
    obiettivo contiene costanti implicite e nessuno sa perché il risultato
    privilegia l'ABV sull'acidità. Con pesi pari a 1 tutti gli obiettivi
    contano uguale *in errore relativo*, che è il confronto corretto fra
    grandezze di unità diverse (frazione, °Bx, % w/v, adimensionale).
    """

    abv: float = 1.0
    brix: float = 1.0
    acidity: float = 1.0
    sugar_acid_ratio: float = 1.0

    def __post_init__(self) -> None:
        for name in ("abv", "brix", "acidity", "sugar_acid_ratio"):
            value = getattr(self, name)
            if value < 0:
                raise SolverError(f"weight '{name}' must not be negative, got {value}")


@dataclass(frozen=True, slots=True)
class TargetProfile:
    """Cosa deve diventare il drink, misurato **dopo** la diluizione.

    I target organolettici si riferiscono al liquido nel bicchiere, non
    alla miscela pre-shake: è ciò che l'ospite beve, ed è l'unico punto in
    cui il modello è falsificabile con un rifrattometro e un alcolimetro.

    `target_volume_ml` è trattato a parte, come vincolo rigido e non come
    obiettivo: la capienza di una coppa non è negoziabile (vedi
    `BalancingSolver`).
    """

    abv: float | None = None
    brix: float | None = None
    acidity: float | None = None
    sugar_acid_ratio: float | None = None
    final_volume_ml: float | None = None

    def __post_init__(self) -> None:
        if self.abv is not None and not 0.0 <= self.abv <= 1.0:
            raise SolverError(f"target abv must be a fraction within [0, 1], got {self.abv}")
        if self.brix is not None and self.brix < 0:
            raise SolverError(f"target brix must not be negative, got {self.brix}")
        if self.acidity is not None and self.acidity < 0:
            raise SolverError(f"target acidity must not be negative, got {self.acidity}")
        if self.sugar_acid_ratio is not None and self.sugar_acid_ratio <= 0:
            raise SolverError(
                f"target sugar_acid_ratio must be greater than 0, " f"got {self.sugar_acid_ratio}"
            )
        if self.final_volume_ml is not None and self.final_volume_ml <= 0:
            raise SolverError(
                f"target final_volume_ml must be greater than 0, got {self.final_volume_ml}"
            )
        if not self.has_objectives and self.final_volume_ml is None:
            raise SolverError("at least one target must be provided")

    @property
    def has_objectives(self) -> bool:
        """True se esiste almeno un obiettivo organolettico da minimizzare.

        Un target di solo volume non è un problema di ottimizzazione: è un
        riscalamento, e il solver lo tratta come tale.
        """
        return any(
            value is not None
            for value in (self.abv, self.brix, self.acidity, self.sugar_acid_ratio)
        )


@dataclass(frozen=True, slots=True)
class SolverSettings:
    """Configurazione numerica della minimizzazione."""

    default_bounds: VolumeBounds = field(default_factory=VolumeBounds)
    #: Bounds specifici per ingrediente, per id. Sovrascrivono `default_bounds`.
    bounds_by_ingredient: dict[str, VolumeBounds] = field(default_factory=dict)
    weights: TargetWeights = field(default_factory=TargetWeights)
    #: Passo di arrotondamento dei volumi finali, in ml. Nessuno versa
    #: 23.7418 ml: 0.5 ml è la risoluzione di un jigger graduato.
    rounding_step_ml: float = 0.5
    max_iterations: int = 200
    tolerance: float = 1e-9
    #: Punti di partenza aggiuntivi, oltre alla ricetta data. SLSQP è un
    #: metodo locale: su un problema non convesso l'esito dipende da dove
    #: si parte, e un multi-start deterministico è l'assicurazione più
    #: economica contro un minimo locale.
    restarts: int = 4
    #: Seme del generatore usato per i punti di ripartenza. Fisso per
    #: default: lo stesso input deve produrre lo stesso output, altrimenti
    #: i test diventano intermittenti e i risultati non riproducibili.
    random_seed: int = 20240914

    def __post_init__(self) -> None:
        if self.rounding_step_ml <= 0:
            raise SolverError("rounding_step_ml must be greater than 0")
        if self.max_iterations <= 0:
            raise SolverError("max_iterations must be greater than 0")
        if self.restarts < 0:
            raise SolverError("restarts must not be negative")

    def bounds_for(self, ingredient_id: str) -> VolumeBounds:
        return self.bounds_by_ingredient.get(ingredient_id, self.default_bounds)


class SolverStatus(str, Enum):
    """Esito della minimizzazione.

    Distinguere i casi è essenziale: una ricetta restituita da un solver
    che non è convergiuto ha lo stesso aspetto di una ottimizzata bene, e
    senza questo campo nessuno a valle può accorgersene.
    """

    #: Ottimo trovato entro la tolleranza richiesta.
    CONVERGED = "CONVERGED"
    #: Iterazioni esaurite: il risultato è il migliore raggiunto, non un ottimo.
    MAX_ITERATIONS = "MAX_ITERATIONS"
    #: Nessun punto rispetta i vincoli (tipicamente volume finale
    #: irraggiungibile entro i bounds dei singoli ingredienti).
    INFEASIBLE = "INFEASIBLE"
    #: Fallimento numerico: la ricetta restituita è quella di partenza.
    FAILED = "FAILED"

    @property
    def is_usable(self) -> bool:
        """True se la ricetta restituita è comunque utilizzabile."""
        return self in (SolverStatus.CONVERGED, SolverStatus.MAX_ITERATIONS)


@dataclass(frozen=True, slots=True)
class TargetResidual:
    """Scarto fra valore ottenuto e valore richiesto per un singolo target."""

    name: str
    target: float
    achieved: float | None

    @property
    def absolute_error(self) -> float | None:
        if self.achieved is None:
            return None
        return abs(self.achieved - self.target)

    @property
    def relative_error(self) -> float | None:
        """Errore relativo al target, la grandezza che il solver minimizza."""
        if self.achieved is None:
            return None
        denominator = abs(self.target) if abs(self.target) > 1e-9 else 1e-9
        return abs(self.achieved - self.target) / denominator


@dataclass(frozen=True, slots=True)
class SolverResult:
    """Esito completo: la ricetta, il suo profilo, e come ci si è arrivati.

    Il `profile` è ricalcolato **sui volumi arrotondati effettivamente
    restituiti**, non su quelli in virgola mobile trovati dal solver: ciò
    che l'API dichiara è ciò che si ottiene versando.
    """

    status: SolverStatus
    recipe: Recipe
    profile: BalanceProfile
    objective_value: float
    iterations: int
    residuals: tuple[TargetResidual, ...]
    message: str
    #: Quante ripartenze hanno prodotto il risultato migliore (0 = il punto
    #: di partenza originale). Serve a capire se il multi-start sta
    #: effettivamente lavorando o se il problema è ben condizionato.
    winning_start: int = 0

    @property
    def max_relative_error(self) -> float | None:
        """Il target peggio servito: il numero da guardare per primo."""
        errors = [
            residual.relative_error
            for residual in self.residuals
            if residual.relative_error is not None
        ]
        return max(errors) if errors else None
