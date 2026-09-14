"""Modello termodinamico di diluizione da ghiaccio (Dave Arnold).

Le due curve sono regressioni quadratiche sui dati sperimentali
pubblicati in *Liquid Intelligence*: misurano quanta acqua di fusione
entra nel drink in funzione della sua gradazione pre-diluizione.

L'andamento non è lineare perché due effetti si oppongono. Più il drink è
alcolico, più abbassa il punto di congelamento della miscela e più
ghiaccio scioglie; ma oltre una certa gradazione la miscela si raffredda
così in fretta da limitare lo scambio termico, e la curva si appiattisce
fino a invertirsi. Da qui il coefficiente quadratico negativo.

L'intercetta non nulla (0.203 shakerato, 0.150 mescolato) è fisica, non un
artefatto: anche un preparato analcolico agitato con ghiaccio si diluisce,
perché lo scambio termico avviene comunque.
"""

from __future__ import annotations

from ..enums import DilutionMethod

# Coefficienti (a, b, c) della forma a·ABV² + b·ABV + c, con ABV in frazione.
_SHAKEN_COEFFICIENTS = (-1.567, 1.742, 0.203)
_STIRRED_COEFFICIENTS = (-1.150, 1.350, 0.150)


def _quadratic(coefficients: tuple[float, float, float], abv: float) -> float:
    a, b, c = coefficients
    return (a * abv * abv) + (b * abv) + c


def shaken_dilution_factor(abv_pre: float) -> float:
    """Frazione di acqua aggiunta agitando con ghiaccio (shake)."""
    return _quadratic(_SHAKEN_COEFFICIENTS, abv_pre)


def stirred_dilution_factor(abv_pre: float) -> float:
    """Frazione di acqua aggiunta mescolando con ghiaccio (stir)."""
    return _quadratic(_STIRRED_COEFFICIENTS, abv_pre)


def dilution_factor(method: DilutionMethod, abv_pre: float) -> float:
    """Fattore di diluizione per la tecnica scelta.

    `BUILT` (costruito direttamente nel bicchiere) restituisce 0: il
    modello di Arnold descrive la diluizione da *preparazione*, mentre un
    built si diluisce durante il consumo, con una dinamica che dipende dal
    tempo di degustazione e non è catturata da queste curve. Trattarlo
    come diluizione nulla rende esplicita l'assunzione: il profilo
    calcolato per un built è quello del drink **appena versato**.
    """
    if method is DilutionMethod.SHAKEN:
        return shaken_dilution_factor(abv_pre)
    if method is DilutionMethod.STIRRED:
        return stirred_dilution_factor(abv_pre)
    return 0.0
