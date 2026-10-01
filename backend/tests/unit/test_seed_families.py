"""La classificazione dei classici del seed deve restare coerente col catalogo."""

from __future__ import annotations

from scripts.seed import CLASSIC_FAMILIES, CLASSICS


def test_every_classified_recipe_exists_in_the_catalogue() -> None:
    # Un refuso nel nome non darebbe errore: il classico resterebbe senza
    # famiglia in silenzio.
    names = {name for name, *_ in CLASSICS}
    assert set(CLASSIC_FAMILIES) <= names
