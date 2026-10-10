"""Classificazione e servizio dei classici del seed coerenti col catalogo."""

from __future__ import annotations

from scripts.seed import CLASSIC_FAMILIES, CLASSIC_GLASSES, CLASSICS

from app.domain.enums import Glassware
from app.domain.glassware_catalogues import glass_model
from app.domain.serving_geometry import ice_fits


def test_every_classified_recipe_exists_in_the_catalogue() -> None:
    # Un refuso nel nome non darebbe errore: il classico resterebbe senza
    # famiglia in silenzio.
    names = {name for name, *_ in CLASSICS}
    assert set(CLASSIC_FAMILIES) <= names


def test_every_classic_is_served_with_ice_that_fits_its_glass() -> None:
    # La ricetta rifiuterebbe la coppia al momento del seed, su un database
    # vero; qui l'incoerenza emerge prima, senza database.
    # I classici usano il catalogo generico.
    misfits = []
    for name, _, ice, *_ in CLASSICS:
        model = glass_model(Glassware.GENERIC, CLASSIC_GLASSES.get(name))
        if not ice_fits(model.profile if model is not None else None, ice):
            misfits.append((name, CLASSIC_GLASSES.get(name), ice))
    assert misfits == []
