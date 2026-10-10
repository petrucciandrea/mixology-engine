"""Bicchieri: capienza, volume utile e verifica del riempimento.

Il bicchiere pone un tetto al volume del drink servito. Il modello ha due
ipotesi dichiarate, da tarare come quelle del ghiaccio di servizio:

1. **Bordo libero.** Nessuno serve a filo: si riempie al più il
   `USABLE_FILL_FRACTION` della capienza, per non versare camminando.
2. **Il ghiaccio occupa spazio.** Con ghiaccio di servizio una quota
   `ICE_SHARE_OF_USABLE_VOLUME` dello spazio utile è ghiaccio solido, e il
   drink ne occupa il resto. Non è `ICE_VOLUME_PER_DRINK_VOLUME` del
   modello di servizio: quella è la massa termica disponibile al
   raffreddamento, questa è lo spazio che il solido sottrae al liquido —
   i cubetti si impilano lasciando vuoti e sporgono sopra il livello, quindi
   spostano meno di quanto la massa farebbe pensare. Il valore è tarato su
   drink classici notoriamente "pieni" (Garibaldi, Cuba Libre) e va rivisto
   con misure reali.

La geometria del bicchiere (misure, e quindi quali ghiacci ci entrano) sta
in `serving_geometry`, perché anche l'aggregate `Recipe` la consulta; qui
il catalogo la mette accanto alla capienza per chi deve scegliere.

Limiti dichiarati: la capienza è un valore tipico per tipo di bicchiere
(le misure reali variano per produttore), e l'acqua di fusione del ghiaccio
di servizio che si aggiunge dopo non è conteggiata — sta nel bordo libero.
`OTHER` non ha capienza nota e quindi non pone alcun limite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..entities import Recipe
from ..enums import GlassType, ServingIce
from ..serving_geometry import compatible_ices

#: Capienza a filo bordo, in ml, per un bicchiere tipico del tipo.
GLASS_CAPACITY_ML: Final[dict[GlassType, float]] = {
    GlassType.COUPE: 200.0,
    GlassType.MARTINI: 240.0,
    GlassType.NICK_AND_NORA: 170.0,
    GlassType.ROCKS: 350.0,
    GlassType.DOUBLE_ROCKS: 450.0,
    GlassType.HIGHBALL: 360.0,
    GlassType.COLLINS: 420.0,
    GlassType.FLUTE: 200.0,
    GlassType.WINE: 350.0,
    GlassType.BALLOON: 600.0,
    GlassType.COPPER_MUG: 400.0,
    GlassType.TIKI: 450.0,
    GlassType.HURRICANE: 450.0,
    GlassType.SHOT: 60.0,
}

#: Quota della capienza riempibile senza rischio di versare.
USABLE_FILL_FRACTION: Final[float] = 0.9

#: Quota dello spazio utile occupata dal ghiaccio solido, quando c'è.
ICE_SHARE_OF_USABLE_VOLUME: Final[float] = 0.35


def max_serving_volume_ml(glass: GlassType, serving_ice: ServingIce) -> float | None:
    """Volume massimo del drink nel bicchiere, o `None` se non c'è un limite."""
    capacity = GLASS_CAPACITY_ML.get(glass)
    if capacity is None:
        return None
    usable = capacity * USABLE_FILL_FRACTION
    if serving_ice is ServingIce.NONE:
        return usable
    return usable * (1.0 - ICE_SHARE_OF_USABLE_VOLUME)


@dataclass(frozen=True, slots=True)
class GlassFit:
    """Quanto il drink riempie il bicchiere in cui è servito."""

    capacity_ml: float
    max_volume_ml: float
    #: Spazio che il ghiaccio di servizio sottrae al drink; 0 senza ghiaccio.
    #: Con `max_volume_ml` fa il volume utile del bicchiere.
    ice_volume_ml: float
    volume_ml: float

    @property
    def fill_ratio(self) -> float:
        """Volume del drink sul massimo ammesso: oltre 1 il drink trabocca."""
        return self.volume_ml / self.max_volume_ml

    @property
    def overflows(self) -> bool:
        return self.volume_ml > self.max_volume_ml


def assess_glass_fit(recipe: Recipe, volume_ml: float) -> GlassFit | None:
    """Riempimento del bicchiere della ricetta, o `None` se non ne ha uno.

    `volume_ml` è il volume del drink servito (`BalanceProfile.final_volume_ml`).
    """
    if recipe.glass is None:
        return None
    max_volume = max_serving_volume_ml(recipe.glass, recipe.serving_ice)
    if max_volume is None:
        return None
    capacity = GLASS_CAPACITY_ML[recipe.glass]
    return GlassFit(
        capacity_ml=capacity,
        max_volume_ml=max_volume,
        ice_volume_ml=capacity * USABLE_FILL_FRACTION - max_volume,
        volume_ml=volume_ml,
    )


@dataclass(frozen=True, slots=True)
class GlassSpec:
    """Un bicchiere come lo vede chi compone: capienza e ghiacci che accoglie."""

    glass: GlassType
    #: `None` per `OTHER`, che non ha capienza nota.
    capacity_ml: float | None
    compatible_ice: tuple[ServingIce, ...]


def glass_catalogue() -> tuple[GlassSpec, ...]:
    """Tutti i bicchieri, nell'ordine dell'enum."""
    return tuple(
        GlassSpec(
            glass=glass,
            capacity_ml=GLASS_CAPACITY_ML.get(glass),
            compatible_ice=compatible_ices(glass),
        )
        for glass in GlassType
    )
