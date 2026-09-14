"""Semantica della sostituzione fra ingredienti.

Due ingredienti che *sanno* uguale non sono necessariamente
intercambiabili. Un succo di lime e uno sciroppo al lime hanno profili
organolettici vicinissimi — stessi descrittori, stesse proporzioni — ma
sostituire l'uno con l'altro sposta l'acidità di sei punti e il Brix di
quaranta: il drink risultante non somiglia all'originale, somiglia a un
errore.

Da qui la separazione, che è il cuore di questo modulo:

* la **similarità organolettica** (coseno sul vettore di sapore) dice se
  due ingredienti *sanno* uguale;
* la **compatibilità fisica** dice se possono occupare lo stesso posto
  nella ricetta senza costringere il solver a ricalcolare tutto.

Un buon candidato alla sostituzione deve avere entrambe. Il punteggio
finale è il loro prodotto, non la loro media: una media lascerebbe
passare un ingrediente perfetto su un asse e assurdo sull'altro, mentre
il prodotto richiede che nessuno dei due sia prossimo a zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from ..entities import Ingredient, PhysicalProfile

# ---------------------------------------------------------------------------
# Scale caratteristiche di ciascun asse fisico.
#
# Servono a rendere confrontabili grandezze di unità diverse: dividere lo
# scarto per la sua scala risponde alla domanda "quanto è grande questa
# differenza *per questo parametro*". I valori sono scelti come la
# differenza che un assaggiatore percepisce chiaramente:
#   * 10 punti di ABV separano un vermouth da uno sherry;
#   * 10 °Bx separano un succo da un liquore;
#   * 1 punto di acidità separa un succo d'arancia da un pompelmo.
#
# La densità è deliberatamente esclusa: nei liquidi da bar è quasi
# interamente determinata dal contenuto zuccherino, quindi includerla
# significherebbe pesare il Brix due volte.
# ---------------------------------------------------------------------------

ABV_SCALE: Final[float] = 0.10
BRIX_SCALE: Final[float] = 10.0
ACIDITY_SCALE: Final[float] = 1.0

#: Sopra questi scarti la sostituzione va segnalata a chi la legge, anche
#: quando il punteggio complessivo resta accettabile.
ABV_WARNING_THRESHOLD: Final[float] = 0.10
BRIX_WARNING_THRESHOLD: Final[float] = 10.0
ACIDITY_WARNING_THRESHOLD: Final[float] = 1.5


@dataclass(frozen=True, slots=True)
class SubstitutionScore:
    """Perché un ingrediente è (o non è) un buon sostituto di un altro.

    I tre numeri restano separati invece di essere fusi in uno solo: chi
    legge deve poter capire *su quale asse* il candidato è debole, perché
    la risposta cambia la decisione. Un sostituto organoletticamente
    lontano ma fisicamente identico si può usare cambiando il carattere
    del drink; uno organoletticamente identico ma fisicamente lontano
    richiede di ridosare, e a quel punto conviene passare dal solver.
    """

    flavor_similarity: float
    physical_compatibility: float
    warnings: tuple[str, ...] = ()

    @property
    def overall(self) -> float:
        """Prodotto dei due assi, in [0, 1]."""
        return self.flavor_similarity * self.physical_compatibility


def physical_distance(left: PhysicalProfile, right: PhysicalProfile) -> float:
    """Distanza euclidea normalizzata sui tre assi che il solver usa.

    Zero significa "stesso comportamento nel bilanciamento". Il valore non
    ha un tetto: due ingredienti possono essere arbitrariamente lontani.
    """
    return math.sqrt(
        ((left.abv - right.abv) / ABV_SCALE) ** 2
        + ((left.brix - right.brix) / BRIX_SCALE) ** 2
        + ((left.acidity - right.acidity) / ACIDITY_SCALE) ** 2
    )


def physical_compatibility(left: PhysicalProfile, right: PhysicalProfile) -> float:
    """Distanza convertita in un punteggio in (0, 1].

    `1 / (1 + d)` invece di un esponenziale: decade più dolcemente, quindi
    non azzera il punteggio di un candidato moderatamente diverso, e resta
    leggibile — a distanza 1 vale esattamente 0.5, cioè "buono a metà".
    """
    return 1.0 / (1.0 + physical_distance(left, right))


def substitution_warnings(original: PhysicalProfile, candidate: PhysicalProfile) -> tuple[str, ...]:
    """Avvertenze in linguaggio da bar, non differenze numeriche grezze.

    Sono scritte perché chi le legge sappia *cosa fare*: "aggiungi acido"
    è azionabile, "acidity delta 5.2" no.
    """
    notes: list[str] = []

    abv_delta = candidate.abv - original.abv
    if abs(abv_delta) >= ABV_WARNING_THRESHOLD:
        direction = "più alcolico" if abv_delta > 0 else "meno alcolico"
        notes.append(
            f"{direction} di {abs(abv_delta) * 100:.0f} punti di ABV: "
            "il drink cambia gradazione, ridosare o ribilanciare"
        )

    brix_delta = candidate.brix - original.brix
    if abs(brix_delta) >= BRIX_WARNING_THRESHOLD:
        if brix_delta > 0:
            notes.append(f"porta {brix_delta:.0f} °Bx in più: ridurre lo zucchero altrove")
        else:
            notes.append(f"porta {abs(brix_delta):.0f} °Bx in meno: il drink risulterà più secco")

    acidity_delta = candidate.acidity - original.acidity
    if abs(acidity_delta) >= ACIDITY_WARNING_THRESHOLD:
        if acidity_delta > 0:
            notes.append(f"aggiunge {acidity_delta:.1f}% di acidità")
        else:
            notes.append(
                f"toglie {abs(acidity_delta):.1f}% di acidità: "
                "reintegrare con succo o soluzione acida"
            )

    return tuple(notes)


def score_substitution(original: Ingredient, candidate: Ingredient) -> SubstitutionScore:
    """Valuta `candidate` come sostituto di `original`.

    Un ingrediente senza profilo organolettico non è un candidato: la sua
    similarità è ignota, non zero, e restituire zero lo farebbe sembrare
    valutato e scartato. Il chiamante lo esclude a monte.
    """
    if original.flavor_profile is None or candidate.flavor_profile is None:
        flavor_similarity = 0.0
    else:
        flavor_similarity = original.flavor_profile.cosine_similarity(candidate.flavor_profile)

    return SubstitutionScore(
        flavor_similarity=flavor_similarity,
        physical_compatibility=physical_compatibility(
            original.physical_profile, candidate.physical_profile
        ),
        warnings=substitution_warnings(original.physical_profile, candidate.physical_profile),
    )
