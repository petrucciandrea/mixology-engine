"""Geometria del servizio: pezzi di ghiaccio, profili dei bicchieri, compatibilità.

Vive accanto a `enums` e non fra i servizi perché è vocabolario: la usano
l'aggregate `Recipe` (per rifiutare un ghiaccio che non entra nel
bicchiere), il bilancio termico del ghiaccio di servizio (superficie e
massa dei pezzi), i cataloghi dei bicchieri e l'API. Importa solo `enums` ed
`errors`, così `entities` può dipenderne senza cicli.

**Ghiaccio.** Un pezzo è un prisma a base quadrata, lato `w` e altezza `h`.
Il cubo è il caso `h = w`; il tritato è trattato come cubi da ~6 mm, che è
la dimensione dei frammenti, non la loro forma.

**Bicchieri (ADR-0013).** Un bicchiere è un solido di rotazione: un profilo
di diametri interni dal fondo della coppa alla bocca. Le schede dei
produttori danno capienza, altezza totale e diametro massimo esterni, quasi
mai la profondità della coppa. Il profilo nasce quindi da tre ingredienti:

1. la **forma** (`GlassShape`), una curva normalizzata `f(t)` con il
   massimo a 1, dal fondo (`t = 0`) alla bocca (`t = 1`);
2. il **diametro massimo interno**, quello della scheda meno due pareti;
3. la **capienza dichiarata**, da cui si ricava la profondità:
   `H = V / (π/4 · D² · ⟨f²⟩)`. Nessuna misura si ritocca per far tornare
   il volume: è il volume a fissare la sola misura che manca.

Quello che non è coppa è stelo e piede, o fondo pieno per un tumbler, e una
scheda che chiedesse una coppa più profonda del bicchiere viene rifiutata.

**Compatibilità.** Un pezzo sta nel bicchiere se ci entra senza sporgere:
deve passare per ogni sezione sopra il punto in cui si appoggia, e si
appoggia alla quota più bassa da cui in su la sezione ne contiene la
diagonale `w·√2` più un gioco. Se da lì non arriva oltre il bordo, entra.
Per un bicchiere che si stringe in alto è la bocca a decidere; per uno che
si allarga, il punto d'appoggio. Il tritato entra ovunque, ed è giusto così.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Final

from .enums import GlassType, ServingIce
from .errors import InvalidServingConditionsError

#: Gioco fra la diagonale del pezzo e la parete: un pezzo che tocca il vetro
#: su tutti gli spigoli non si mette nel bicchiere, si incastra.
ICE_CLEARANCE_MM: Final[float] = 4.0

#: Spessore della parete, uguale per tutti: il cristallo da hospitality sta
#: fra 1.5 e 2.5 mm. Serve a passare dal diametro esterno della scheda a
#: quello interno, che è quello che conta per volume e ghiaccio.
WALL_THICKNESS_MM: Final[float] = 2.0

#: Il fondo più sottile ammesso sotto la coppa: sotto questo spessore la
#: scheda è incoerente (troppa capienza per quelle misure).
MIN_BOTTOM_MM: Final[float] = 3.0

#: Campioni del profilo, dal fondo alla bocca: abbastanza per seguire le
#: curve di coppe e tulipani, pochi per l'API e il disegno.
PROFILE_SEGMENTS: Final[int] = 48


def _require_dimensions(*values: float) -> None:
    if not all(math.isfinite(value) and value > 0.0 for value in values):
        raise InvalidServingConditionsError(
            f"dimensions must be finite and positive, got {values!r}"
        )


# --- Ghiaccio -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IcePiece:
    """Un pezzo di ghiaccio di servizio, prisma a base quadrata.

    `is_single` distingue il ghiaccio che *riempie* il bicchiere (cubetti,
    tritato: la quantità segue il drink) dal pezzo unico (cubo grosso,
    colonna: la quantità è il pezzo stesso, qualunque sia il drink).
    """

    width_mm: float
    height_mm: float
    is_single: bool

    def __post_init__(self) -> None:
        _require_dimensions(self.width_mm, self.height_mm)

    @property
    def volume_ml(self) -> float:
        return self.width_mm**2 * self.height_mm / 1000.0

    @property
    def surface_m2(self) -> float:
        """Due basi quadrate e quattro facce laterali."""
        return (2.0 * self.width_mm**2 + 4.0 * self.width_mm * self.height_mm) * 1e-6

    @property
    def specific_surface_m2_per_m3(self) -> float:
        """S/V: per un cubo di lato `a` vale 6/a."""
        return self.surface_m2 / (self.volume_ml * 1e-6)

    @property
    def diagonal_mm(self) -> float:
        """Ingombro della sezione: il cerchio che contiene il quadrato di lato `w`."""
        return self.width_mm * math.sqrt(2.0)


#: Cubetti da 25 mm, cubo grosso da 50 mm, tritato in frammenti da ~6 mm,
#: colonna da 30 × 30 × 120 mm (il "Collins spear").
ICE_PIECES: Final[dict[ServingIce, IcePiece]] = {
    ServingIce.CUBES: IcePiece(width_mm=25.0, height_mm=25.0, is_single=False),
    ServingIce.LARGE_CUBE: IcePiece(width_mm=50.0, height_mm=50.0, is_single=True),
    ServingIce.CRUSHED: IcePiece(width_mm=6.0, height_mm=6.0, is_single=False),
    ServingIce.SPEAR: IcePiece(width_mm=30.0, height_mm=120.0, is_single=True),
}


# --- Profilo del bicchiere ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GlassProfile:
    """Il vano del liquido: diametri interni a quote equispaziate.

    `diameters_mm[0]` è il fondo della coppa, l'ultimo la bocca; fra due
    campioni il diametro varia linearmente. Il volume si integra sullo
    stesso profilo (sezioni circolari, regola dei trapezi su `d²`), così
    profilo e capienza non possono disaccordarsi.
    """

    depth_mm: float
    diameters_mm: tuple[float, ...]

    def __post_init__(self) -> None:
        _require_dimensions(self.depth_mm)
        if len(self.diameters_mm) < 2:
            raise InvalidServingConditionsError("a glass profile needs at least two diameters")
        if not all(math.isfinite(d) and d >= 0.0 for d in self.diameters_mm):
            raise InvalidServingConditionsError(
                f"profile diameters must be finite and non-negative, got {self.diameters_mm!r}"
            )
        if self.diameters_mm[-1] <= 0.0:
            raise InvalidServingConditionsError("a glass must have an open mouth")

    @property
    def _step_mm(self) -> float:
        return self.depth_mm / (len(self.diameters_mm) - 1)

    def width_at(self, height_mm: float) -> float:
        """Diametro interno a quota `height_mm` dal fondo della coppa."""
        position = min(max(height_mm / self._step_mm, 0.0), len(self.diameters_mm) - 1.0)
        index = min(int(position), len(self.diameters_mm) - 2)
        share = position - index
        below, above = self.diameters_mm[index], self.diameters_mm[index + 1]
        return below + (above - below) * share

    @property
    def mouth_diameter_mm(self) -> float:
        return self.diameters_mm[-1]

    @property
    def max_diameter_mm(self) -> float:
        return max(self.diameters_mm)

    @property
    def volume_ml(self) -> float:
        return self.depth_mm * _mean_square(self.diameters_mm) * math.pi / 4.0 / 1000.0


def _mean_square(values: tuple[float, ...]) -> float:
    """⟨d²⟩ sui campioni, con la regola dei trapezi."""
    squares = [value**2 for value in values]
    inner = sum(squares[1:-1])
    return (inner + (squares[0] + squares[-1]) / 2.0) / (len(squares) - 1)


# --- Forme --------------------------------------------------------------------


class GlassShape(str, Enum):
    """Famiglie di forma: la curva del profilo, a meno della scala.

    Non sono i tipi di bicchiere (`GlassType`): un highball e un Collins
    sono entrambi tumbler, e un Martini moderno può essere una coppa.
    """

    TUMBLER = "TUMBLER"
    COUPE = "COUPE"
    CONE = "CONE"
    BELL = "BELL"
    TULIP = "TULIP"
    BALLOON = "BALLOON"
    FLUTE = "FLUTE"
    TIKI = "TIKI"
    HURRICANE = "HURRICANE"


#: Le forme con stelo: quello che non è coppa è stelo e piede.
STEMMED_SHAPES: Final[frozenset[GlassShape]] = frozenset(
    {
        GlassShape.COUPE,
        GlassShape.CONE,
        GlassShape.BELL,
        GlassShape.TULIP,
        GlassShape.BALLOON,
        GlassShape.FLUTE,
        GlassShape.HURRICANE,
    }
)

#: Bocca / diametro massimo, per le forme che si stringono in alto, quando
#: la scheda non la dà. Valori tipici, segnalati come stima.
DEFAULT_RIM_RATIO: Final[dict[GlassShape, float]] = {
    GlassShape.TULIP: 0.78,
    GlassShape.BALLOON: 0.78,
    GlassShape.HURRICANE: 0.92,
}

#: Fondo / bocca per un tumbler, quando la scheda non lo dà: la leggera
#: rastremazione dei tumbler da bar.
DEFAULT_BASE_RATIO: Final[float] = 0.92


def _lerp(start: float, end: float, share: float) -> float:
    return start + (end - start) * share


def _tulip(widest: float, rim: float) -> Callable[[float], float]:
    """Fondo arrotondato (quarto d'ellisse) fino al massimo a quota `widest`,
    poi chiusura a coseno fino alla bocca, `rim` volte il massimo."""

    def width(t: float) -> float:
        if t <= widest:
            return math.sqrt(max(0.0, 1.0 - ((widest - t) / widest) ** 2))
        return rim + (1.0 - rim) * math.cos((t - widest) / (1.0 - widest) * math.pi / 2.0)

    return width


def _through(points: tuple[tuple[float, float], ...]) -> Callable[[float], float]:
    """Curva liscia per punti di controllo, raccordati a coseno."""

    def width(t: float) -> float:
        for (t0, w0), (t1, w1) in zip(points, points[1:], strict=False):
            if t <= t1:
                share = (1.0 - math.cos((t - t0) / (t1 - t0) * math.pi)) / 2.0
                return _lerp(w0, w1, share)
        return points[-1][1]

    return width


def _shape_curve(
    shape: GlassShape, rim_ratio: float, base_ratio: float
) -> Callable[[float], float]:
    match shape:
        case GlassShape.TUMBLER:
            return lambda t: _lerp(base_ratio, 1.0, t)
        case GlassShape.COUPE:
            return lambda t: math.sqrt(max(0.0, 1.0 - (1.0 - t) ** 2))
        case GlassShape.CONE:
            return lambda t: t
        case GlassShape.BELL:
            return lambda t: math.sqrt(max(0.0, 1.0 - (1.0 - t) ** 2.2))
        case GlassShape.TULIP:
            return _tulip(0.42, rim_ratio)
        case GlassShape.BALLOON:
            return _tulip(0.45, rim_ratio)
        case GlassShape.FLUTE:
            return lambda t: _lerp(0.35, 1.0, math.sqrt(t))
        case GlassShape.TIKI:
            return lambda t: 0.78 + 0.22 * math.sin(math.pi * (0.9 * t + 0.05))
        case GlassShape.HURRICANE:
            # Bulbo in basso, vita, svasatura verso la bocca.
            return _through(((0.0, 0.72), (0.25, 1.0), (0.6, 0.72), (1.0, rim_ratio)))


# --- Modello di bicchiere ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GlassModel:
    """Un bicchiere reale di un catalogo, come lo descrive la sua scheda.

    Le misure sono quelle pubblicate (esterne, capienza a colmo); `source`
    dice dove. Rapporti di forma che la scheda non dà prendono un valore
    tipico, e `estimated` li elenca: chi legge il catalogo deve poter
    distinguere un dato da un'ipotesi.
    """

    glass: GlassType
    product: str
    capacity_ml: float
    #: Altezza totale esterna, piede compreso.
    height_mm: float
    #: Diametro massimo esterno.
    diameter_mm: float
    shape: GlassShape
    source: str
    #: Bocca / massimo, per le forme che si stringono in alto.
    rim_ratio: float | None = None
    #: Fondo / bocca, per i tumbler.
    base_ratio: float | None = None
    profile: GlassProfile = field(init=False, compare=False)

    def __post_init__(self) -> None:
        _require_dimensions(self.capacity_ml, self.height_mm, self.diameter_mm)
        if not self.product.strip() or not self.source.strip():
            raise InvalidServingConditionsError("a glass model needs a product name and a source")
        for ratio in (self.rim_ratio, self.base_ratio):
            if ratio is not None and not (0.0 < ratio <= 1.0):
                raise InvalidServingConditionsError(f"shape ratios must be in (0, 1], got {ratio}")
        inner = self.diameter_mm - 2.0 * WALL_THICKNESS_MM
        _require_dimensions(inner)

        curve = _shape_curve(
            self.shape,
            self.rim_ratio
            if self.rim_ratio is not None
            else DEFAULT_RIM_RATIO.get(self.shape, 1.0),
            self.base_ratio if self.base_ratio is not None else DEFAULT_BASE_RATIO,
        )
        diameters = tuple(
            inner * curve(index / PROFILE_SEGMENTS) for index in range(PROFILE_SEGMENTS + 1)
        )
        # La curva ha il massimo a 1 per costruzione, ma campionata può
        # mancarlo di poco: si riscala perché il massimo sia quello vero.
        peak = max(diameters)
        diameters = tuple(d * inner / peak for d in diameters)
        depth = self.capacity_ml * 1000.0 / (math.pi / 4.0 * _mean_square(diameters))
        if depth > self.height_mm - MIN_BOTTOM_MM:
            raise InvalidServingConditionsError(
                f"{self.product}: a {self.capacity_ml} ml bowl would be {depth:.0f} mm deep, "
                f"deeper than the {self.height_mm} mm glass"
            )
        object.__setattr__(self, "profile", GlassProfile(depth_mm=depth, diameters_mm=diameters))

    @property
    def is_stemmed(self) -> bool:
        return self.shape in STEMMED_SHAPES

    @property
    def stem_mm(self) -> float:
        """Stelo e piede sotto la coppa; 0 per un bicchiere senza stelo."""
        return self.height_mm - self.profile.depth_mm if self.is_stemmed else 0.0

    @property
    def base_mm(self) -> float:
        """Fondo pieno sotto il liquido; 0 per un bicchiere a stelo."""
        return 0.0 if self.is_stemmed else self.height_mm - self.profile.depth_mm

    @property
    def estimated(self) -> tuple[str, ...]:
        """I rapporti di forma presi per ipotesi invece che dalla scheda."""
        guesses = []
        if self.shape in DEFAULT_RIM_RATIO and self.rim_ratio is None:
            guesses.append("rim_ratio")
        if self.shape is GlassShape.TUMBLER and self.base_ratio is None:
            guesses.append("base_ratio")
        return tuple(guesses)


# --- Compatibilità ------------------------------------------------------------------


def _resting_height_mm(profile: GlassProfile, needed_mm: float) -> float | None:
    """La quota più bassa da cui in su ogni sezione è larga almeno `needed_mm`.

    `None` se nemmeno la bocca lo è: il pezzo non entra proprio.
    """
    diameters = profile.diameters_mm
    if diameters[-1] < needed_mm:
        return None
    step = profile.depth_mm / (len(diameters) - 1)
    for index in range(len(diameters) - 1, 0, -1):
        below, above = diameters[index - 1], diameters[index]
        if below < needed_mm:
            # Qui la sezione scende sotto il necessario: il punto d'appoggio
            # è dove il segmento lo attraversa.
            return (index - 1 + (needed_mm - below) / (above - below)) * step
    return 0.0


def ice_fits(profile: GlassProfile | None, ice: ServingIce) -> bool:
    """Il ghiaccio `ice` sta nel bicchiere senza sporgere né incastrarsi.

    Senza profilo (nessun bicchiere, o uno senza misure come `OTHER`) non
    c'è nulla su cui giudicare e nessun ghiaccio è escluso.
    """
    if ice is ServingIce.NONE or profile is None:
        return True
    piece = ICE_PIECES[ice]
    resting = _resting_height_mm(profile, piece.diagonal_mm + ICE_CLEARANCE_MM)
    return resting is not None and resting + piece.height_mm <= profile.depth_mm


def compatible_ices(profile: GlassProfile | None) -> tuple[ServingIce, ...]:
    """I ghiacci che stanno nel bicchiere, nell'ordine dell'enum."""
    return tuple(ice for ice in ServingIce if ice_fits(profile, ice))
