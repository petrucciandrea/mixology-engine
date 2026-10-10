"""Cataloghi di bicchieri: coerenza dei dati delle schede.

Il dominio è finito, quindi le verifiche si fanno **su tutto** invece di
campionarle: ogni bicchiere di ogni catalogo. Sono controlli sui dati come
lo sarebbero su una tabella di laboratorio: misure positive, una fonte per
ciascuno, una coppa che sta nel bicchiere e contiene la capienza
dichiarata. Le aspettative "da banco" (il cubo grosso non entra in un
Collins, la colonna non sta in un tumbler basso) devono valere per ogni
linea, non solo per quella generica.
"""

from __future__ import annotations

import pytest

from app.domain.enums import GlassType, Glassware, ServingIce
from app.domain.glassware_catalogues import CATALOGUES, GENERIC, glass_model
from app.domain.serving_geometry import MIN_BOTTOM_MM, GlassModel, ice_fits

MODELS = [
    (catalogue.glassware, model)
    for catalogue in CATALOGUES.values()
    for model in catalogue.models.values()
]


def _id(item: tuple[Glassware, GlassModel]) -> str:
    return f"{item[0].value}-{item[1].glass.value}"


class TestCatalogues:
    def test_every_glassware_has_a_catalogue(self) -> None:
        assert set(CATALOGUES) == set(Glassware)

    def test_generic_covers_every_measurable_type(self) -> None:
        assert set(GENERIC.models) == set(GlassType) - {GlassType.OTHER}

    def test_no_catalogue_measures_other(self) -> None:
        for catalogue in CATALOGUES.values():
            assert GlassType.OTHER not in catalogue.models

    def test_models_are_filed_under_their_own_type(self) -> None:
        for catalogue in CATALOGUES.values():
            for glass, model in catalogue.models.items():
                assert model.glass is glass

    def test_glass_model_lookup(self) -> None:
        assert (
            glass_model(Glassware.NUDE, GlassType.COUPE)
            is CATALOGUES[Glassware.NUDE].models[GlassType.COUPE]
        )
        assert glass_model(Glassware.NUDE, GlassType.TIKI) is None
        assert glass_model(Glassware.GENERIC, None) is None
        assert glass_model(Glassware.GENERIC, GlassType.OTHER) is None

    def test_brand_lines_cite_a_web_source(self) -> None:
        for glassware, model in MODELS:
            if glassware is not Glassware.GENERIC:
                assert model.source.startswith("https://"), model.product


@pytest.mark.parametrize("item", MODELS, ids=_id)
class TestEveryGlass:
    def test_the_bowl_holds_the_declared_capacity(self, item: tuple[Glassware, GlassModel]) -> None:
        _, model = item
        assert model.profile.volume_ml == pytest.approx(model.capacity_ml)

    def test_the_bowl_fits_inside_the_glass(self, item: tuple[Glassware, GlassModel]) -> None:
        _, model = item
        assert model.profile.depth_mm <= model.height_mm - MIN_BOTTOM_MM
        assert model.profile.max_diameter_mm < model.diameter_mm

    def test_neat_and_crushed_are_always_possible(self, item: tuple[Glassware, GlassModel]) -> None:
        _, model = item
        assert ice_fits(model.profile, ServingIce.NONE)
        assert ice_fits(model.profile, ServingIce.CRUSHED)


class TestBarExpectations:
    """Le regole che un barman darebbe per scontate, su ogni linea."""

    @pytest.mark.parametrize("glassware", list(Glassware))
    def test_a_large_cube_never_enters_a_collins_or_a_small_cup(self, glassware: Glassware) -> None:
        for glass in (GlassType.COLLINS, GlassType.COUPE, GlassType.NICK_AND_NORA):
            model = glass_model(glassware, glass)
            if model is not None:
                assert not ice_fits(model.profile, ServingIce.LARGE_CUBE), model.product

    @pytest.mark.parametrize("glassware", list(Glassware))
    def test_a_spear_never_stands_in_a_low_tumbler(self, glassware: Glassware) -> None:
        for glass in (GlassType.ROCKS, GlassType.DOUBLE_ROCKS):
            model = glass_model(glassware, glass)
            if model is not None:
                assert not ice_fits(model.profile, ServingIce.SPEAR), model.product

    @pytest.mark.parametrize("glassware", list(Glassware))
    def test_a_double_rocks_takes_a_large_cube(self, glassware: Glassware) -> None:
        model = glass_model(glassware, GlassType.DOUBLE_ROCKS)
        assert model is not None
        assert ice_fits(model.profile, ServingIce.LARGE_CUBE), model.product
