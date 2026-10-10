"""Geometria del servizio: pezzi di ghiaccio, bicchieri e compatibilità.

I valori attesi si calcolano a mano dalle misure dichiarate: un pezzo è un
prisma a base quadrata (lato `w`, altezza `h`), un bicchiere un tronco di
cono (diametro del fondo `d`, della bocca `D`, profondità `H`). Il pezzo
entra se non sporge (`h ≤ H`) e se la sezione del bicchiere, alla quota a
cui si appoggia, ne contiene la diagonale `w·√2` più il gioco.
"""

from __future__ import annotations

import math

import pytest

from app.domain.enums import GlassType, ServingIce
from app.domain.errors import InvalidServingConditionsError
from app.domain.services.glassware import GLASS_CAPACITY_ML
from app.domain.serving_geometry import (
    GLASS_GEOMETRY,
    ICE_CLEARANCE_MM,
    ICE_PIECES,
    GlassGeometry,
    IcePiece,
    compatible_ices,
    ice_fits,
)

ICED = [ice for ice in ServingIce if ice is not ServingIce.NONE]
SIZED_GLASSES = [glass for glass in GlassType if glass is not GlassType.OTHER]


class TestIcePiece:
    def test_a_cube_has_specific_surface_six_over_its_side(self) -> None:
        cube = IcePiece(width_mm=25.0, height_mm=25.0, is_single=False)
        # S/V = 6/a con a = 0.025 m → 240 m⁻¹.
        assert cube.specific_surface_m2_per_m3 == pytest.approx(240.0)
        assert cube.volume_ml == pytest.approx(15.625)

    def test_a_spear_is_a_square_prism(self) -> None:
        spear = ICE_PIECES[ServingIce.SPEAR]
        # 30 × 30 × 120 mm: V = 108 000 mm³, S = 2·30² + 4·30·120 = 16 200 mm².
        assert spear.volume_ml == pytest.approx(108.0)
        assert spear.surface_m2 == pytest.approx(0.0162)
        assert spear.specific_surface_m2_per_m3 == pytest.approx(150.0)
        assert spear.is_single

    def test_the_diagonal_of_the_cross_section_bounds_the_fit(self) -> None:
        assert ICE_PIECES[ServingIce.LARGE_CUBE].diagonal_mm == pytest.approx(50.0 * math.sqrt(2))

    def test_single_pieces_and_fill_ice(self) -> None:
        assert ICE_PIECES[ServingIce.LARGE_CUBE].is_single
        assert ICE_PIECES[ServingIce.SPEAR].is_single
        assert not ICE_PIECES[ServingIce.CUBES].is_single
        assert not ICE_PIECES[ServingIce.CRUSHED].is_single

    def test_finer_ice_exposes_more_surface(self) -> None:
        surface = {ice: ICE_PIECES[ice].specific_surface_m2_per_m3 for ice in ICED}
        assert (
            surface[ServingIce.CRUSHED]
            > surface[ServingIce.CUBES]
            > surface[ServingIce.SPEAR]
            > surface[ServingIce.LARGE_CUBE]
        )

    def test_none_has_no_piece(self) -> None:
        assert ServingIce.NONE not in ICE_PIECES

    @pytest.mark.parametrize(("width", "height"), [(0.0, 10.0), (10.0, -1.0), (math.nan, 10.0)])
    def test_rejects_impossible_dimensions(self, width: float, height: float) -> None:
        with pytest.raises(InvalidServingConditionsError, match="dimensions"):
            IcePiece(width_mm=width, height_mm=height, is_single=False)


class TestGlassGeometry:
    def test_a_cylinder_has_the_same_width_at_every_height(self) -> None:
        cylinder = GlassGeometry(bottom_diameter_mm=80.0, mouth_diameter_mm=80.0, depth_mm=90.0)
        assert cylinder.width_at(0.0) == cylinder.width_at(90.0) == 80.0
        # π/4 · 80² · 90 = 452 389 mm³.
        assert cylinder.volume_ml == pytest.approx(452.389, rel=1e-5)

    def test_a_cone_widens_linearly_from_the_bottom(self) -> None:
        cone = GlassGeometry(bottom_diameter_mm=0.0, mouth_diameter_mm=115.0, depth_mm=70.0)
        assert cone.width_at(35.0) == pytest.approx(57.5)
        # Cono: π/12 · D² · H.
        assert cone.volume_ml == pytest.approx(math.pi / 12 * 115.0**2 * 70.0 / 1000.0)

    def test_rejects_impossible_dimensions(self) -> None:
        with pytest.raises(InvalidServingConditionsError, match="dimensions"):
            GlassGeometry(bottom_diameter_mm=50.0, mouth_diameter_mm=0.0, depth_mm=90.0)

    @pytest.mark.parametrize("glass", SIZED_GLASSES)
    def test_dimensions_agree_with_the_declared_capacity(self, glass: GlassType) -> None:
        """Le misure non sono indipendenti dalla capienza: il tronco di cono
        deve contenere quanto il bicchiere dichiara, entro il 10%."""
        assert GLASS_GEOMETRY[glass].volume_ml == pytest.approx(GLASS_CAPACITY_ML[glass], rel=0.10)

    def test_other_has_no_geometry(self) -> None:
        assert GlassType.OTHER not in GLASS_GEOMETRY


class TestIceFits:
    def test_without_ice_every_glass_works(self) -> None:
        for glass in GlassType:
            assert ice_fits(glass, ServingIce.NONE)

    def test_without_a_glass_or_with_an_unknown_one_nothing_is_excluded(self) -> None:
        for ice in ServingIce:
            assert ice_fits(None, ice)
            assert ice_fits(GlassType.OTHER, ice)

    def test_a_large_cube_does_not_enter_a_collins(self) -> None:
        # Diagonale 70.7 mm + 4 di gioco contro una bocca da 62 mm.
        collins = GLASS_GEOMETRY[GlassType.COLLINS]
        assert collins.mouth_diameter_mm < 50.0 * math.sqrt(2) + ICE_CLEARANCE_MM
        assert not ice_fits(GlassType.COLLINS, ServingIce.LARGE_CUBE)

    @pytest.mark.parametrize("glass", [GlassType.COUPE, GlassType.NICK_AND_NORA])
    def test_a_large_cube_does_not_sit_in_a_small_cup(self, glass: GlassType) -> None:
        assert not ice_fits(glass, ServingIce.LARGE_CUBE)

    def test_a_spear_sticks_out_of_a_rocks_glass(self) -> None:
        assert GLASS_GEOMETRY[GlassType.ROCKS].depth_mm < 120.0
        assert not ice_fits(GlassType.ROCKS, ServingIce.SPEAR)

    @pytest.mark.parametrize("glass", [GlassType.COLLINS, GlassType.HIGHBALL])
    def test_a_spear_is_made_for_tall_narrow_glasses(self, glass: GlassType) -> None:
        assert ice_fits(glass, ServingIce.SPEAR)

    def test_a_large_cube_fits_a_rocks_glass(self) -> None:
        assert ice_fits(GlassType.ROCKS, ServingIce.LARGE_CUBE)

    def test_in_a_cone_the_piece_sits_where_the_section_holds_it(self) -> None:
        """Martini (cono da 115 × 70 mm): un cubetto da 25 mm si appoggia
        dove la sezione vale 35.4 + 4 mm, cioè a quota 24 mm, e arriva a
        49 mm, sotto il bordo; il cubo grosso dovrebbe appoggiarsi a 45.5 mm
        e arrivare a 95.5, ben oltre."""
        assert ice_fits(GlassType.MARTINI, ServingIce.CUBES)
        assert not ice_fits(GlassType.MARTINI, ServingIce.LARGE_CUBE)

    def test_a_narrow_mouth_stops_a_piece_even_if_the_belly_could_hold_it(self) -> None:
        """Calice: pancia da 75 mm, bocca da 65. Il cubo grosso ci starebbe
        sul fondo, ma non passa dalla bocca."""
        wine = GLASS_GEOMETRY[GlassType.WINE]
        assert wine.bottom_diameter_mm >= 50.0 * math.sqrt(2) + ICE_CLEARANCE_MM - 1.0
        assert not ice_fits(GlassType.WINE, ServingIce.LARGE_CUBE)

    @pytest.mark.parametrize("glass", SIZED_GLASSES)
    def test_crushed_ice_fits_every_glass(self, glass: GlassType) -> None:
        assert ice_fits(glass, ServingIce.CRUSHED)


class TestCompatibleIces:
    def test_lists_only_what_fits_in_enum_order(self) -> None:
        assert compatible_ices(GlassType.ROCKS) == (
            ServingIce.NONE,
            ServingIce.CUBES,
            ServingIce.LARGE_CUBE,
            ServingIce.CRUSHED,
        )
        assert compatible_ices(GlassType.COLLINS) == (
            ServingIce.NONE,
            ServingIce.CUBES,
            ServingIce.CRUSHED,
            ServingIce.SPEAR,
        )

    @pytest.mark.parametrize("glass", [*GlassType, None])
    def test_serving_neat_is_always_possible(self, glass: GlassType | None) -> None:
        assert ServingIce.NONE in compatible_ices(glass)

    def test_no_glass_means_no_restriction(self) -> None:
        assert compatible_ices(None) == tuple(ServingIce)
