"""Classificazione e servizio dei classici del seed coerenti col catalogo."""

from __future__ import annotations

from scripts.seed import (
    BAR,
    CLASSIC_FAMILIES,
    CLASSIC_GLASSES,
    CLASSICS,
    SUPERSEDED_GLASSES,
    physical_profile_of,
)

from app.domain.entities import Ingredient, Recipe, RecipeIngredient
from app.domain.enums import Glassware
from app.domain.glassware_catalogues import glass_model
from app.domain.services.balance_calculator import calculate_balance
from app.domain.services.glassware import assess_glass_fit
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


def test_every_classic_fits_its_glass() -> None:
    """Ogni classico, al dosaggio canonico e diluito, entra nel suo bicchiere
    generico insieme al suo ghiaccio. Si costruisce dalle schede del seed,
    senza database: è la verifica che una nuova capienza o un nuovo modello
    del ghiaccio non faccia traboccare un classico in silenzio."""
    catalogue = {
        spec.name: Ingredient(
            id=f"seed-{index}",
            name=spec.name,
            category=spec.category,
            physical_profile=physical_profile_of(spec),
        )
        for index, spec in enumerate(BAR)
    }
    overflowing = []
    for name, method, ice, _, doses in CLASSICS:
        recipe = Recipe(
            id=name,
            name=name,
            dilution_method=method,
            serving_ice=ice,
            glass=CLASSIC_GLASSES.get(name),
            ingredients=tuple(
                RecipeIngredient(ingredient=catalogue[item], volume_ml=volume)
                for item, volume in doses
            ),
        )
        fit = assess_glass_fit(recipe, calculate_balance(recipe).final_volume_ml)
        if fit is not None and fit.overflows:
            overflowing.append((name, f"{fit.fill_ratio:.0%}"))
    assert overflowing == []


def test_glass_revisions_name_classics_that_moved() -> None:
    # Una revisione che non sposta nulla è un residuo: non fa nulla e
    # confonde chi legge.
    for name, old_glass in SUPERSEDED_GLASSES.items():
        assert CLASSIC_GLASSES[name] is not old_glass, name
