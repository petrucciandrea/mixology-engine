"""Bicchieri: volume utile e verifica del riempimento.

I valori attesi sono calcolati a mano dalle ipotesi dichiarate: bordo
libero del 10% (`USABLE_FILL_FRACTION`) e, con ghiaccio di servizio, una
quota di spazio utile occupata dal ghiaccio (`ICE_SHARE_OF_USABLE_VOLUME`
= 0.35), per cui il drink ne occupa il 65%. La capienza è quella del
bicchiere nel catalogo della ricetta.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.domain.entities import Recipe
from app.domain.enums import GlassType, Glassware, ServingIce
from app.domain.glassware_catalogues import CATALOGUES, GENERIC, glass_model
from app.domain.services.balance_calculator import calculate_balance
from app.domain.services.glassware import (
    USABLE_FILL_FRACTION,
    assess_glass_fit,
    max_serving_volume_ml,
    recipe_volume_cap_ml,
)
from app.domain.serving_geometry import GlassModel

ALL_MODELS = [model for catalogue in CATALOGUES.values() for model in catalogue.models.values()]


class TestRecipeGlass:
    def test_the_glass_is_optional(self, daiquiri: Recipe) -> None:
        assert daiquiri.glass is None

    def test_a_recipe_carries_its_glass_and_catalogue(self, daiquiri: Recipe) -> None:
        coupe = replace(daiquiri, glass=GlassType.COUPE, glassware=Glassware.NUDE)
        assert coupe.glass is GlassType.COUPE
        assert coupe.glassware is Glassware.NUDE

    def test_the_catalogue_defaults_to_generic(self, daiquiri: Recipe) -> None:
        assert daiquiri.glassware is Glassware.GENERIC

    def test_with_volumes_preserves_glass_and_catalogue(self, daiquiri: Recipe) -> None:
        coupe = replace(daiquiri, glass=GlassType.COUPE, glassware=Glassware.SCHOTT_ZWIESEL)
        moved = coupe.with_volumes([50.0, 25.0, 15.0])
        assert moved.glass is GlassType.COUPE
        assert moved.glassware is Glassware.SCHOTT_ZWIESEL


class TestMaxServingVolume:
    def test_a_neat_drink_may_fill_the_glass_up_to_the_headspace(self) -> None:
        coupe = GENERIC.models[GlassType.COUPE]
        # 210 ml × 0.9 = 189 ml
        assert max_serving_volume_ml(coupe, ServingIce.NONE) == pytest.approx(189.0)

    def test_ice_takes_a_share_of_the_usable_space(self) -> None:
        highball = GENERIC.models[GlassType.HIGHBALL]
        # 350 × 0.9 × (1 − 0.35) = 204.75 ml di drink.
        assert max_serving_volume_ml(highball, ServingIce.CUBES) == pytest.approx(204.75)

    def test_the_cap_follows_the_catalogue(self, daiquiri: Recipe) -> None:
        """Lo stesso tipo, due linee, due capienze: è il motivo per cui la
        ricetta ricorda il catalogo."""
        generic = replace(daiquiri, glass=GlassType.COUPE)
        nude = replace(daiquiri, glass=GlassType.COUPE, glassware=Glassware.NUDE)
        assert recipe_volume_cap_ml(generic) == pytest.approx(210.0 * USABLE_FILL_FRACTION)
        assert recipe_volume_cap_ml(nude) == pytest.approx(222.0 * USABLE_FILL_FRACTION)

    def test_no_glass_or_other_means_no_cap(self, daiquiri: Recipe) -> None:
        assert recipe_volume_cap_ml(daiquiri) is None
        assert recipe_volume_cap_ml(replace(daiquiri, glass=GlassType.OTHER)) is None

    @pytest.mark.parametrize("model", ALL_MODELS, ids=lambda m: m.product)
    def test_ice_never_raises_the_cap(self, model: GlassModel) -> None:
        neat = max_serving_volume_ml(model, ServingIce.NONE)
        assert 0 < max_serving_volume_ml(model, ServingIce.CUBES) < neat
        assert neat <= model.capacity_ml


class TestAssessGlassFit:
    def test_none_without_a_glass(self, daiquiri: Recipe) -> None:
        assert assess_glass_fit(daiquiri, calculate_balance(daiquiri).final_volume_ml) is None

    def test_none_for_a_glass_without_measures(self, daiquiri: Recipe) -> None:
        other = replace(daiquiri, glass=GlassType.OTHER)
        assert assess_glass_fit(other, 100.0) is None

    def test_a_daiquiri_fits_a_coupe(self, daiquiri: Recipe) -> None:
        coupe = replace(daiquiri, glass=GlassType.COUPE)
        fit = assess_glass_fit(coupe, calculate_balance(coupe).final_volume_ml)

        assert fit is not None
        assert fit.capacity_ml == 210.0
        assert fit.max_volume_ml == pytest.approx(189.0)
        assert not fit.overflows
        assert fit.fill_ratio == pytest.approx(fit.volume_ml / 189.0)

    def test_the_same_daiquiri_overflows_a_shot_glass(self, daiquiri: Recipe) -> None:
        shot = replace(daiquiri, glass=GlassType.SHOT)
        fit = assess_glass_fit(shot, calculate_balance(shot).final_volume_ml)

        assert fit is not None
        assert fit.overflows
        assert fit.fill_ratio > 1.0

    def test_exactly_at_the_limit_does_not_overflow(self, daiquiri: Recipe) -> None:
        coupe = replace(daiquiri, glass=GlassType.COUPE)
        fit = assess_glass_fit(coupe, 189.0)

        assert fit is not None
        assert fit.fill_ratio == pytest.approx(1.0)
        assert not fit.overflows

    def test_ice_and_drink_share_the_usable_volume(self, daiquiri: Recipe) -> None:
        rocks = replace(daiquiri, glass=GlassType.ROCKS, serving_ice=ServingIce.CUBES)
        fit = assess_glass_fit(rocks, 100.0)

        assert fit is not None
        # Tumbler basso generico 300 ml: 300 × 0.9 × 0.35 = 94.5 ml di
        # ghiaccio, e insieme al drink massimo fanno il volume utile, 270 ml.
        assert fit.ice_volume_ml == pytest.approx(94.5)
        assert fit.max_volume_ml + fit.ice_volume_ml == pytest.approx(270.0)

    def test_uses_the_catalogue_of_the_recipe(self, daiquiri: Recipe) -> None:
        recipe = replace(daiquiri, glass=GlassType.COUPE, glassware=Glassware.LUIGI_BORMIOLI)
        fit = assess_glass_fit(recipe, 100.0)
        model = glass_model(Glassware.LUIGI_BORMIOLI, GlassType.COUPE)

        assert fit is not None and model is not None
        assert fit.capacity_ml == model.capacity_ml == 225.0
