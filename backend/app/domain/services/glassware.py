"""Bicchieri: volume utile e verifica del riempimento.

Il bicchiere pone un tetto al volume del drink servito. Capienza e misure
vengono dal modello del catalogo della ricetta (`glassware_catalogues`,
ADR-0013); qui restano le due ipotesi sul servizio, da tarare come quelle
del ghiaccio:

1. **Bordo libero.** Nessuno serve a filo: si riempie al più il
   `USABLE_FILL_FRACTION` della capienza, per non versare camminando.
2. **Il ghiaccio occupa spazio**, in due modi diversi (ADR-0013).
   - Il **pezzo unico** (cubo grosso, colonna) è un solido che sta tutto
     sotto il bordo — la compatibilità lo garantisce — e sottrae al drink
     esattamente il suo volume.
   - Il ghiaccio che **riempie** (cubetti, tritato) occupa una quota
     `ICE_SHARE_OF_USABLE_VOLUME` dello spazio utile. Non è
     `ICE_VOLUME_PER_DRINK_VOLUME` del modello di servizio: quella è la
     massa termica disponibile al raffreddamento, questa è lo spazio che il
     solido sottrae al liquido — i cubetti si impilano lasciando vuoti e
     sporgono sopra il livello, quindi spostano meno di quanto la massa
     farebbe pensare.

Limiti dichiarati: l'acqua di fusione del ghiaccio di servizio che si
aggiunge dopo non è conteggiata (sta nel bordo libero), e la quota del
ghiaccio di riempimento è tarata, non misurata. `OTHER`, senza misure, non
pone limiti.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..entities import Recipe
from ..enums import ServingIce
from ..glassware_catalogues import glass_model
from ..serving_geometry import ICE_PIECES, GlassModel

#: Quota della capienza riempibile senza rischio di versare.
USABLE_FILL_FRACTION: Final[float] = 0.9

#: Quota dello spazio utile occupata dal ghiaccio solido, quando c'è.
ICE_SHARE_OF_USABLE_VOLUME: Final[float] = 0.35


def ice_space_ml(model: GlassModel, serving_ice: ServingIce) -> float:
    """Spazio che il ghiaccio di servizio sottrae al drink nel bicchiere."""
    if serving_ice is ServingIce.NONE:
        return 0.0
    piece = ICE_PIECES[serving_ice]
    if piece.is_single:
        return piece.volume_ml
    return model.capacity_ml * USABLE_FILL_FRACTION * ICE_SHARE_OF_USABLE_VOLUME


def max_serving_volume_ml(model: GlassModel, serving_ice: ServingIce) -> float:
    """Volume massimo del drink nel bicchiere, accanto al suo ghiaccio."""
    return model.capacity_ml * USABLE_FILL_FRACTION - ice_space_ml(model, serving_ice)


def recipe_volume_cap_ml(recipe: Recipe) -> float | None:
    """Tetto al volume del drink per la ricetta, o `None` se non ce n'è uno."""
    model = glass_model(recipe.glassware, recipe.glass)
    return None if model is None else max_serving_volume_ml(model, recipe.serving_ice)


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
    """Riempimento del bicchiere della ricetta, o `None` se non ne ha uno
    con misure note.

    `volume_ml` è il volume del drink servito (`BalanceProfile.final_volume_ml`).
    """
    model = glass_model(recipe.glassware, recipe.glass)
    if model is None:
        return None
    max_volume = max_serving_volume_ml(model, recipe.serving_ice)
    return GlassFit(
        capacity_ml=model.capacity_ml,
        max_volume_ml=max_volume,
        ice_volume_ml=ice_space_ml(model, recipe.serving_ice),
        volume_ml=volume_ml,
    )
