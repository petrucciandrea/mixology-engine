"""Bicchieri: capienza, volume utile e verifica del riempimento.

I valori attesi sono calcolati a mano dalle ipotesi dichiarate: bordo
libero del 10% (`USABLE_FILL_FRACTION`) e, con ghiaccio di servizio, un
quota di spazio utile occupata dal ghiaccio (`ICE_SHARE_OF_USABLE_VOLUME`
= 0.35), per cui il drink ne occupa il 65%.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.domain.entities import Recipe
from app.domain.enums import GlassType, ServingIce
from app.domain.services.balance_calculator import calculate_balance
from app.domain.services.glassware import (
    GLASS_CAPACITY_ML,
    USABLE_FILL_FRACTION,
    assess_glass_fit,
    max_serving_volume_ml,
)

#: Tutti i bicchieri con una capienza nota, cioè tutti tranne `OTHER`.
SIZED_GLASSES = [glass for glass in GlassType if glass is not GlassType.OTHER]


class TestRecipeGlass:
    def test_the_glass_is_optional(self, daiquiri: Recipe) -> None:
        assert daiquiri.glass is None

    def test_a_recipe_carries_its_glass(self, daiquiri: Recipe) -> None:
        assert replace(daiquiri, glass=GlassType.COUPE).glass is GlassType.COUPE

    def test_with_volumes_preserves_the_glass(self, daiquiri: Recipe) -> None:
        coupe = replace(daiquiri, glass=GlassType.COUPE)
        assert coupe.with_volumes([50.0, 25.0, 15.0]).glass is GlassType.COUPE


class TestCapacityTable:
    def test_every_glass_but_other_has_a_positive_capacity(self) -> None:
        for glass in GlassType:
            if glass is GlassType.OTHER:
                assert glass not in GLASS_CAPACITY_ML
            else:
                assert GLASS_CAPACITY_ML[glass] > 0

    def test_other_has_no_capacity_and_therefore_no_limit(self) -> None:
        assert max_serving_volume_ml(GlassType.OTHER, ServingIce.NONE) is None


class TestMaxServingVolume:
    def test_a_neat_drink_may_fill_the_glass_up_to_the_headspace(self) -> None:
        # 200 ml × 0.9 = 180 ml
        assert max_serving_volume_ml(GlassType.COUPE, ServingIce.NONE) == pytest.approx(
            GLASS_CAPACITY_ML[GlassType.COUPE] * USABLE_FILL_FRACTION
        )
        assert max_serving_volume_ml(GlassType.COUPE, ServingIce.NONE) == pytest.approx(180.0)

    @pytest.mark.parametrize("ice", [ServingIce.CUBES, ServingIce.LARGE_CUBE, ServingIce.CRUSHED])
    def test_ice_takes_a_share_of_the_usable_space(self, ice: ServingIce) -> None:
        # Highball 360 ml: 360 × 0.9 × (1 − 0.35) = 210.6 ml di drink.
        assert max_serving_volume_ml(GlassType.HIGHBALL, ice) == pytest.approx(210.6)

    def test_a_bigger_glass_holds_more(self) -> None:
        small = max_serving_volume_ml(GlassType.SHOT, ServingIce.NONE)
        large = max_serving_volume_ml(GlassType.TIKI, ServingIce.NONE)
        assert small is not None and large is not None
        assert small < large


class TestInvariants:
    """Il dominio è finito, quindi le invarianti si verificano **su tutto** invece
    di campionarle: ogni bicchiere, con e senza ghiaccio."""

    @pytest.mark.parametrize("glass", SIZED_GLASSES)
    @pytest.mark.parametrize("ice", list(ServingIce))
    def test_the_cap_is_positive_and_never_above_the_capacity(
        self, glass: GlassType, ice: ServingIce
    ) -> None:
        cap = max_serving_volume_ml(glass, ice)

        assert cap is not None
        assert 0 < cap <= GLASS_CAPACITY_ML[glass] * USABLE_FILL_FRACTION

    @pytest.mark.parametrize("glass", SIZED_GLASSES)
    def test_ice_never_raises_the_cap(self, glass: GlassType) -> None:
        neat = max_serving_volume_ml(glass, ServingIce.NONE)
        assert neat is not None
        for ice in (ServingIce.CUBES, ServingIce.LARGE_CUBE, ServingIce.CRUSHED):
            iced = max_serving_volume_ml(glass, ice)
            assert iced is not None
            assert iced < neat


class TestAssessGlassFit:
    def test_none_without_a_glass(self, daiquiri: Recipe) -> None:
        assert assess_glass_fit(daiquiri, calculate_balance(daiquiri).final_volume_ml) is None

    def test_none_for_a_glass_without_capacity(self, daiquiri: Recipe) -> None:
        other = replace(daiquiri, glass=GlassType.OTHER)
        assert assess_glass_fit(other, 100.0) is None

    def test_a_daiquiri_fits_a_coupe(self, daiquiri: Recipe) -> None:
        coupe = replace(daiquiri, glass=GlassType.COUPE)
        fit = assess_glass_fit(coupe, calculate_balance(coupe).final_volume_ml)

        assert fit is not None
        assert fit.capacity_ml == 200.0
        assert fit.max_volume_ml == pytest.approx(180.0)
        assert not fit.overflows
        assert fit.fill_ratio == pytest.approx(fit.volume_ml / 180.0)
        assert fit.fill_ratio < 1.0

    def test_the_same_daiquiri_overflows_a_shot_glass(self, daiquiri: Recipe) -> None:
        shot = replace(daiquiri, glass=GlassType.SHOT)
        fit = assess_glass_fit(shot, calculate_balance(shot).final_volume_ml)

        assert fit is not None
        assert fit.overflows
        assert fit.fill_ratio > 1.0

    def test_exactly_at_the_limit_does_not_overflow(self, daiquiri: Recipe) -> None:
        coupe = replace(daiquiri, glass=GlassType.COUPE)
        fit = assess_glass_fit(coupe, 180.0)

        assert fit is not None
        assert fit.fill_ratio == pytest.approx(1.0)
        assert not fit.overflows

    def test_a_neat_drink_leaves_no_room_to_ice(self, daiquiri: Recipe) -> None:
        coupe = replace(daiquiri, glass=GlassType.COUPE)
        fit = assess_glass_fit(coupe, 100.0)

        assert fit is not None
        assert fit.ice_volume_ml == 0.0

    def test_ice_and_drink_share_the_usable_volume(self, daiquiri: Recipe) -> None:
        rocks = replace(daiquiri, glass=GlassType.ROCKS, serving_ice=ServingIce.CUBES)
        fit = assess_glass_fit(rocks, 100.0)

        assert fit is not None
        # Tumbler basso 350 ml: 350 × 0.9 × 0.35 = 110.25 ml di ghiaccio,
        # e insieme al drink massimo fanno il volume utile, 315 ml.
        assert fit.ice_volume_ml == pytest.approx(110.25)
        assert fit.max_volume_ml + fit.ice_volume_ml == pytest.approx(315.0)
