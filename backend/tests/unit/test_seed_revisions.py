"""Le revisioni dei dati fisici del seed raggiungono i database già popolati."""

from __future__ import annotations

from dataclasses import replace

import pytest
from scripts.seed import (
    BAR,
    SUPERSEDED_PROFILES,
    Spec,
    physical_profile_of,
    revised_profile,
)

from app.domain.entities import Ingredient, PhysicalProfile
from app.domain.enums import IngredientCategory

SPECS = {spec.name: spec for spec in BAR}


def _stored(spec: Spec, profile: PhysicalProfile) -> Ingredient:
    return Ingredient(
        id=f"id-{spec.name}", name=spec.name, category=spec.category, physical_profile=profile
    )


def test_every_superseded_profile_names_an_ingredient_that_changed() -> None:
    # Una voce che non esiste più, o il cui valore nuovo è uguale al vecchio,
    # è un residuo: non fa nulla e confonde chi legge.
    assert set(SUPERSEDED_PROFILES) <= set(SPECS)
    for name, old in SUPERSEDED_PROFILES.items():
        assert physical_profile_of(SPECS[name]) != old, name


def test_lime_juice_carries_sugar_only_not_the_refractometer_reading() -> None:
    """Un lime a 7.5 °Bx contava ~5 g di zucchero ogni 100 g che non esistono.

    Il resto della lettura è acido citrico (6 % × ~0.9 °Bx per punto), che il
    modello conta già come acidità: contarlo anche come zucchero rende
    dolci i drink a base di lime.
    """
    lime = SPECS["Succo di Lime"]
    lemon = SPECS["Succo di Limone"]

    assert lime.brix < 3.0
    # Il limone era già a soli zuccheri: i due agrumi devono essere confrontabili.
    assert lime.brix == pytest.approx(lemon.brix, abs=1.5)


def test_an_untouched_stored_profile_is_realigned() -> None:
    spec = SPECS["Succo di Lime"]
    stored = _stored(spec, SUPERSEDED_PROFILES["Succo di Lime"])

    assert revised_profile(stored, spec) == physical_profile_of(spec)


def test_a_profile_edited_by_the_user_is_left_alone() -> None:
    spec = SPECS["Succo di Lime"]
    customised = replace(SUPERSEDED_PROFILES["Succo di Lime"], acidity=5.0)

    assert revised_profile(_stored(spec, customised), spec) is None


def test_an_already_realigned_profile_is_a_no_op() -> None:
    spec = SPECS["Succo di Lime"]

    assert revised_profile(_stored(spec, physical_profile_of(spec)), spec) is None


def test_an_ingredient_without_a_revision_is_never_touched() -> None:
    spec = next(s for s in BAR if s.category is IngredientCategory.SPIRIT)

    assert revised_profile(_stored(spec, physical_profile_of(spec)), spec) is None
