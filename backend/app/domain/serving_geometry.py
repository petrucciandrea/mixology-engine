"""Geometria del servizio: pezzi di ghiaccio, bicchieri e compatibilità.

Vive accanto a `enums` e non fra i servizi perché è vocabolario: la usano
l'aggregate `Recipe` (per rifiutare un ghiaccio che non entra nel
bicchiere), il bilancio termico del ghiaccio di servizio (superficie e
massa dei pezzi) e l'API (che espone la matrice di compatibilità). Importa
solo `enums`, così `entities` può dipenderne senza cicli.

Il modello ha due semplificazioni dichiarate:

1. **Un pezzo di ghiaccio è un prisma a base quadrata**, lato `w` e
   altezza `h`. Il cubo è il caso `h = w`; il tritato è trattato come cubi
   da ~6 mm, che è la dimensione dei frammenti, non la loro forma.
2. **Un bicchiere è un tronco di cono**: diametro interno del fondo, della
   bocca e profondità del vano. Basta per i bicchieri dritti (tumbler,
   highball), per il cono del Martini e, con la pancia al posto del fondo,
   per quelli che si stringono verso la bocca (calice, balloon). Le misure
   sono tipiche per tipo, come le capienze di `services/glassware`, e i test
   verificano che le due tabelle si accordino.

**Regola di compatibilità.** Un pezzo sta nel bicchiere se ci entra senza
sporgere: deve passare dalla bocca, e appoggiato il più in alto possibile
(`z = H − h`, il bordo superiore a filo) la sezione a quella quota deve
contenerne la diagonale `w·√2` più un gioco. In un bicchiere che si allarga
verso l'alto (`width` crescente) la quota più alta è anche la più larga, e
se il pezzo non ci sta lì non ci sta da nessuna parte; in uno che si
stringe è la bocca a decidere. Per il tritato la regola è sempre
soddisfatta, ed è giusto così: si adatta a qualunque bicchiere.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from .enums import GlassType, ServingIce
from .errors import InvalidServingConditionsError

#: Gioco fra la diagonale del pezzo e la parete: un pezzo che tocca il vetro
#: su tutti gli spigoli non si mette nel bicchiere, si incastra.
ICE_CLEARANCE_MM: Final[float] = 4.0


def _require_dimensions(*values: float) -> None:
    if not all(math.isfinite(value) and value > 0.0 for value in values):
        raise InvalidServingConditionsError(
            f"dimensions must be finite and positive, got {values!r}"
        )


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


@dataclass(frozen=True, slots=True)
class GlassGeometry:
    """Il vano del liquido di un bicchiere, come tronco di cono.

    Il fondo può valere zero (il cono del Martini); la bocca e la
    profondità no. Se il fondo è più largo della bocca, il bicchiere si
    stringe verso l'alto.
    """

    bottom_diameter_mm: float
    mouth_diameter_mm: float
    depth_mm: float

    def __post_init__(self) -> None:
        _require_dimensions(self.mouth_diameter_mm, self.depth_mm)
        if not (math.isfinite(self.bottom_diameter_mm) and self.bottom_diameter_mm >= 0.0):
            raise InvalidServingConditionsError(
                f"dimensions must be finite and non-negative, got {self.bottom_diameter_mm!r}"
            )

    def width_at(self, height_mm: float) -> float:
        """Diametro interno a quota `height_mm` dal fondo."""
        share = height_mm / self.depth_mm
        return self.bottom_diameter_mm + (self.mouth_diameter_mm - self.bottom_diameter_mm) * share

    @property
    def volume_ml(self) -> float:
        """Tronco di cono: π·H/12 · (D² + D·d + d²)."""
        d, big_d = self.bottom_diameter_mm, self.mouth_diameter_mm
        return math.pi * self.depth_mm / 12.0 * (big_d**2 + big_d * d + d**2) / 1000.0


#: Misure interne tipiche, in mm: (fondo, bocca, profondità). Per i calici
#: e il balloon il "fondo" è la pancia, il punto più largo.
GLASS_GEOMETRY: Final[dict[GlassType, GlassGeometry]] = {
    glass: GlassGeometry(bottom_diameter_mm=bottom, mouth_diameter_mm=mouth, depth_mm=depth)
    for glass, (bottom, mouth, depth) in {
        GlassType.COUPE: (40.0, 110.0, 45.0),
        GlassType.MARTINI: (0.0, 115.0, 70.0),
        GlassType.NICK_AND_NORA: (35.0, 75.0, 70.0),
        GlassType.ROCKS: (75.0, 85.0, 70.0),
        GlassType.DOUBLE_ROCKS: (80.0, 90.0, 80.0),
        GlassType.HIGHBALL: (60.0, 64.0, 125.0),
        GlassType.COLLINS: (58.0, 62.0, 150.0),
        GlassType.FLUTE: (30.0, 58.0, 130.0),
        GlassType.WINE: (75.0, 65.0, 90.0),
        GlassType.BALLOON: (100.0, 75.0, 100.0),
        GlassType.COPPER_MUG: (85.0, 85.0, 72.0),
        GlassType.TIKI: (80.0, 80.0, 90.0),
        GlassType.HURRICANE: (55.0, 75.0, 140.0),
        GlassType.SHOT: (34.0, 40.0, 55.0),
    }.items()
}


def ice_fits(glass: GlassType | None, ice: ServingIce) -> bool:
    """Il ghiaccio `ice` sta nel bicchiere `glass` senza sporgere né incastrarsi.

    Senza bicchiere, o con un bicchiere senza misure (`OTHER`), non c'è
    nulla su cui giudicare e nessun ghiaccio è escluso: è la stessa
    convenzione della capienza.
    """
    if ice is ServingIce.NONE or glass is None:
        return True
    geometry = GLASS_GEOMETRY.get(glass)
    if geometry is None:
        return True
    piece = ICE_PIECES[ice]
    if piece.height_mm > geometry.depth_mm:
        return False
    needed = piece.diagonal_mm + ICE_CLEARANCE_MM
    resting_width = geometry.width_at(geometry.depth_mm - piece.height_mm)
    return min(geometry.mouth_diameter_mm, resting_width) >= needed


def compatible_ices(glass: GlassType | None) -> tuple[ServingIce, ...]:
    """I ghiacci che stanno nel bicchiere, nell'ordine dell'enum."""
    return tuple(ice for ice in ServingIce if ice_fits(glass, ice))
