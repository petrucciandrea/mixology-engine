"""Tassonomia organolettica e vettore di sapore.

Decisione di progetto (ADR-005): il profilo organolettico di un
ingrediente è un vettore **a descrittori espliciti**, non un embedding
testuale prodotto da un modello linguistico.

Motivazioni:

1. *Interpretabilità*. Ogni componente ha un nome e un significato
   verificabile da un assaggiatore: la similarità fra due ingredienti si
   può spiegare ("differiscono soprattutto su `smoke` e `warm_spice`"),
   mentre due embedding vicini nello spazio di un modello linguistico
   dicono solo che le *descrizioni testuali* si somigliano.
2. *Determinismo*. Lo stesso ingrediente produce sempre lo stesso vettore,
   quindi i test sono ripetibili e le migrazioni non dipendono dalla
   versione di un modello.
3. *Peso operativo*. Non trascina `torch` nell'immagine Docker, che su
   Mac Intel x86_64 costerebbe qualche GB e minuti di build.

Il costo è che i vettori vanno compilati a mano (o derivati da schede di
degustazione strutturate) invece di essere generati automaticamente.

La dimensione del vettore è parte dello schema del database: la colonna
`vector(32)` non può cambiare senza una migrazione, quindi
`FLAVOR_DESCRIPTORS` va trattata come un contratto versionato. Aggiungere
un descrittore significa scrivere una migrazione che riscrive la colonna.

Ogni componente è un'intensità normalizzata in [0, 1]: 0 = assente,
1 = descrittore dominante dell'ingrediente.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from .errors import InvalidFlavorProfileError

#: Gusti fondamentali percepiti dalle papille (asse gustativo).
BASIC_TASTE_DESCRIPTORS: Final[tuple[str, ...]] = (
    "sweet",
    "sour",
    "bitter",
    "salty",
    "umami",
)

#: Sensazioni trigeminali e tattili: non sono gusti né aromi, ma
#: determinano quanto due ingredienti siano intercambiabili in bocca.
TACTILE_DESCRIPTORS: Final[tuple[str, ...]] = (
    "alcohol_heat",
    "astringency",
    "cooling",
    "pungency",
)

#: Famiglie aromatiche (asse olfattivo/retrolfattivo).
AROMA_DESCRIPTORS: Final[tuple[str, ...]] = (
    "citrus",
    "orchard_fruit",
    "stone_fruit",
    "berry",
    "tropical_fruit",
    "dried_fruit",
    "floral",
    "herbaceous",
    "mint",
    "anise",
    "resinous",
    "pepper",
    "warm_spice",
    "earthy",
    "woody",
    "vanilla",
    "caramel",
    "smoke",
    "roasted",
    "nutty",
    "honey",
    "funky",
    "medicinal",
)

#: Contratto completo del vettore, nell'ordine in cui le componenti
#: compaiono nella colonna `vector` di PostgreSQL. L'ordine è
#: significativo: non riordinare senza una migrazione dei dati.
FLAVOR_DESCRIPTORS: Final[tuple[str, ...]] = (
    BASIC_TASTE_DESCRIPTORS + TACTILE_DESCRIPTORS + AROMA_DESCRIPTORS
)

FLAVOR_VECTOR_DIMENSION: Final[int] = len(FLAVOR_DESCRIPTORS)

_DESCRIPTOR_INDEX: Final[dict[str, int]] = {
    name: position for position, name in enumerate(FLAVOR_DESCRIPTORS)
}


@dataclass(frozen=True, slots=True)
class FlavorProfile:
    """Vettore organolettico di un ingrediente.

    Value object immutabile: due profili con le stesse componenti sono lo
    stesso profilo. La similarità del coseno è definita qui, nel dominio,
    perché è la *semantica* della vicinanza organolettica; il fatto che in
    produzione il calcolo venga delegato a pgvector per efficienza è un
    dettaglio infrastrutturale, e questa implementazione resta il
    riferimento contro cui verificarlo.
    """

    components: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.components) != FLAVOR_VECTOR_DIMENSION:
            raise InvalidFlavorProfileError(
                f"flavor profile must have exactly {FLAVOR_VECTOR_DIMENSION} "
                f"components, got {len(self.components)}"
            )
        for name, value in zip(FLAVOR_DESCRIPTORS, self.components, strict=True):
            if not math.isfinite(value):
                raise InvalidFlavorProfileError(f"descriptor '{name}' is not a finite number")
            if not 0.0 <= value <= 1.0:
                raise InvalidFlavorProfileError(
                    f"descriptor '{name}' must be within [0.0, 1.0], got {value}"
                )

    @classmethod
    def from_descriptors(cls, **descriptors: float) -> FlavorProfile:
        """Costruisce un profilo nominando solo i descrittori non nulli.

        Scrivere a mano 32 zeri è illeggibile e fragile; questo costruttore
        è il modo previsto per definire un ingrediente:

            FlavorProfile.from_descriptors(sour=0.9, citrus=0.85)

        Un descrittore non riconosciuto è un errore, non un silenzio: è la
        protezione contro i refusi in un vocabolario di 32 nomi.
        """
        unknown = sorted(set(descriptors) - set(_DESCRIPTOR_INDEX))
        if unknown:
            raise InvalidFlavorProfileError(f"unknown flavor descriptors: {', '.join(unknown)}")
        components = [0.0] * FLAVOR_VECTOR_DIMENSION
        for name, value in descriptors.items():
            components[_DESCRIPTOR_INDEX[name]] = value
        return cls(components=tuple(components))

    @classmethod
    def neutral(cls) -> FlavorProfile:
        """Profilo nullo: usato per acqua e per ingredienti non ancora profilati."""
        return cls(components=(0.0,) * FLAVOR_VECTOR_DIMENSION)

    def as_dict(self) -> dict[str, float]:
        """Rappresentazione nominata, per API e diagnostica."""
        return dict(zip(FLAVOR_DESCRIPTORS, self.components, strict=True))

    def dominant(self, limit: int = 5) -> tuple[tuple[str, float], ...]:
        """I descrittori più intensi, dal più forte — la "firma" del sapore."""
        present = [(name, value) for name, value in self.as_dict().items() if value > 0.0]
        present.sort(key=lambda item: (-item[1], item[0]))
        return tuple(present[:limit])

    @property
    def magnitude(self) -> float:
        return math.sqrt(sum(value * value for value in self.components))

    def cosine_similarity(self, other: FlavorProfile) -> float:
        """Similarità del coseno in [0, 1].

        Le componenti sono non negative, quindi il coseno non può essere
        negativo: 0 significa nessun descrittore in comune, 1 significa
        stessa direzione organolettica (eventualmente con intensità
        complessiva diversa — il coseno ignora la magnitudine, ed è
        esattamente ciò che serve per la sostituzione fra ingredienti).
        Un profilo nullo non ha direzione: la similarità è 0 per
        convenzione, non indefinita.
        """
        left = self.magnitude
        right = other.magnitude
        if left == 0.0 or right == 0.0:
            return 0.0
        dot = sum(a * b for a, b in zip(self.components, other.components, strict=True))
        # Il clamp assorbe l'errore di arrotondamento in virgola mobile, che
        # su vettori identici può restituire 1.0000000000000002.
        return max(0.0, min(1.0, dot / (left * right)))
