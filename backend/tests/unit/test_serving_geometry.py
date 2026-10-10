"""Geometria del servizio: pezzi di ghiaccio, profili dei bicchieri, compatibilità.

I valori attesi si calcolano a mano. Un pezzo di ghiaccio è un prisma a
base quadrata (lato `w`, altezza `h`). Un bicchiere è un solido di
rotazione: un profilo `d(t)` di diametri dal fondo (`t = 0`) alla bocca
(`t = 1`) e una profondità `H`, ricavata dalla capienza dichiarata,
`H = V / (π/4 · ⟨d²⟩)`. Un pezzo entra se, appoggiato dove la sezione ne
contiene la diagonale `w·√2` più il gioco, non sporge dal bordo.
"""

from __future__ import annotations

import math

import pytest

from app.domain.enums import GlassType, ServingIce
from app.domain.errors import InvalidServingConditionsError
from app.domain.serving_geometry import (
    ICE_CLEARANCE_MM,
    ICE_PIECES,
    WALL_THICKNESS_MM,
    GlassModel,
    GlassProfile,
    GlassShape,
    IcePiece,
    compatible_ices,
    ice_fits,
)

ICED = [ice for ice in ServingIce if ice is not ServingIce.NONE]


def _cylinder(diameter_mm: float, depth_mm: float) -> GlassProfile:
    return GlassProfile(depth_mm=depth_mm, diameters_mm=(diameter_mm,) * 9)


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


class TestGlassProfile:
    def test_a_cylinder_holds_its_section_times_its_depth(self) -> None:
        cylinder = _cylinder(80.0, 90.0)
        # π/4 · 80² · 90 = 452 389 mm³.
        assert cylinder.volume_ml == pytest.approx(452.389, rel=1e-5)
        assert cylinder.width_at(0.0) == cylinder.width_at(90.0) == 80.0
        assert cylinder.mouth_diameter_mm == cylinder.max_diameter_mm == 80.0

    def test_width_is_interpolated_between_samples(self) -> None:
        cone = GlassProfile(depth_mm=100.0, diameters_mm=(0.0, 50.0, 100.0))
        assert cone.width_at(25.0) == pytest.approx(25.0)
        assert cone.width_at(75.0) == pytest.approx(75.0)

    def test_rejects_impossible_profiles(self) -> None:
        with pytest.raises(InvalidServingConditionsError):
            GlassProfile(depth_mm=0.0, diameters_mm=(50.0, 50.0))
        with pytest.raises(InvalidServingConditionsError):
            GlassProfile(depth_mm=90.0, diameters_mm=(50.0,))
        with pytest.raises(InvalidServingConditionsError):
            GlassProfile(depth_mm=90.0, diameters_mm=(50.0, 0.0))


class TestGlassModel:
    """La scheda dà misure esterne e capienza; la profondità della coppa si
    ricava, così il profilo contiene esattamente la capienza dichiarata."""

    def _tumbler(self, base_ratio: float = 1.0) -> GlassModel:
        return GlassModel(
            glass=GlassType.ROCKS,
            product="Tumbler di prova",
            capacity_ml=300.0,
            height_mm=100.0,
            diameter_mm=84.0,
            shape=GlassShape.TUMBLER,
            source="https://example.com/tumbler",
            base_ratio=base_ratio,
        )

    def test_a_cylindrical_tumbler_gets_its_depth_from_the_capacity(self) -> None:
        model = self._tumbler()
        inner = 84.0 - 2 * WALL_THICKNESS_MM
        # H = 300 000 mm³ / (π/4 · 80²) = 59.68 mm.
        assert model.profile.depth_mm == pytest.approx(300_000.0 / (math.pi / 4 * inner**2))
        assert model.profile.volume_ml == pytest.approx(300.0)
        assert model.profile.max_diameter_mm == pytest.approx(inner)

    def test_what_is_not_the_bowl_is_base_or_stem(self) -> None:
        model = self._tumbler()
        assert model.base_mm == pytest.approx(100.0 - model.profile.depth_mm)
        assert not model.is_stemmed

    def test_a_tapered_tumbler_is_narrower_at_the_bottom(self) -> None:
        model = self._tumbler(base_ratio=0.8)
        profile = model.profile
        assert profile.width_at(0.0) == pytest.approx(0.8 * profile.mouth_diameter_mm)
        assert profile.volume_ml == pytest.approx(300.0)
        # Meno sezione in basso: per la stessa capienza serve più profondità.
        assert profile.depth_mm > self._tumbler().profile.depth_mm

    def test_a_cone_follows_its_diameter_linearly(self) -> None:
        cone = GlassModel(
            glass=GlassType.MARTINI,
            product="Martini di prova",
            capacity_ml=200.0,
            height_mm=170.0,
            diameter_mm=104.0,
            shape=GlassShape.CONE,
            source="https://example.com/martini",
        )
        inner = 104.0 - 2 * WALL_THICKNESS_MM
        # Cono: V = π/12 · D² · H. Il profilo campionato lo approssima.
        assert cone.profile.depth_mm == pytest.approx(
            200_000.0 / (math.pi / 12 * inner**2), rel=0.01
        )
        assert cone.is_stemmed
        assert cone.stem_mm == pytest.approx(170.0 - cone.profile.depth_mm)

    def test_a_tulip_closes_towards_the_mouth(self) -> None:
        wine = GlassModel(
            glass=GlassType.WINE,
            product="Calice di prova",
            capacity_ml=350.0,
            height_mm=220.0,
            diameter_mm=84.0,
            shape=GlassShape.TULIP,
            source="https://example.com/calice",
            rim_ratio=0.75,
        )
        profile = wine.profile
        # Il massimo campionato può mancare di un soffio quello della curva.
        assert profile.mouth_diameter_mm == pytest.approx(0.75 * profile.max_diameter_mm, rel=1e-3)
        assert profile.mouth_diameter_mm < profile.max_diameter_mm

    def test_declared_ratios_are_not_estimates_defaults_are(self) -> None:
        def tulip(rim_ratio: float | None) -> GlassModel:
            return GlassModel(
                glass=GlassType.WINE,
                product="Calice",
                capacity_ml=350.0,
                height_mm=220.0,
                diameter_mm=84.0,
                shape=GlassShape.TULIP,
                source="https://example.com/calice",
                rim_ratio=rim_ratio,
            )

        assert "rim_ratio" in tulip(None).estimated
        assert "rim_ratio" not in tulip(0.7).estimated

    def test_rejects_a_bowl_deeper_than_the_glass(self) -> None:
        """Una scheda incoerente (troppa capienza per quelle misure) non deve
        produrre un bicchiere impossibile in silenzio."""
        with pytest.raises(InvalidServingConditionsError, match="deeper"):
            GlassModel(
                glass=GlassType.SHOT,
                product="Bicchierino incoerente",
                capacity_ml=500.0,
                height_mm=60.0,
                diameter_mm=45.0,
                shape=GlassShape.TUMBLER,
                source="https://example.com/shot",
            )


class TestIceFits:
    def test_without_ice_or_without_a_profile_everything_fits(self) -> None:
        assert ice_fits(_cylinder(30.0, 20.0), ServingIce.NONE)
        for ice in ServingIce:
            assert ice_fits(None, ice)

    def test_a_large_cube_needs_its_diagonal_plus_clearance(self) -> None:
        needed = 50.0 * math.sqrt(2) + ICE_CLEARANCE_MM
        assert ice_fits(_cylinder(needed + 0.1, 80.0), ServingIce.LARGE_CUBE)
        assert not ice_fits(_cylinder(needed - 0.1, 80.0), ServingIce.LARGE_CUBE)

    def test_a_piece_must_not_stick_out(self) -> None:
        assert ice_fits(_cylinder(60.0, 121.0), ServingIce.SPEAR)
        assert not ice_fits(_cylinder(60.0, 119.0), ServingIce.SPEAR)

    def test_in_a_cone_the_piece_sits_where_the_section_holds_it(self) -> None:
        """Cono da 115 mm di bocca e 70 di profondità: un cubetto da 25 mm
        si appoggia dove la sezione vale 35.4 + 4 mm (quota 24 mm) e arriva
        a 49 mm; il cubo grosso si appoggerebbe a 45.5 mm e arriverebbe a
        95.5, oltre il bordo."""
        cone = GlassProfile(depth_mm=70.0, diameters_mm=(0.0, 115.0))
        assert ice_fits(cone, ServingIce.CUBES)
        assert not ice_fits(cone, ServingIce.LARGE_CUBE)

    def test_a_narrow_mouth_stops_a_piece_the_belly_could_hold(self) -> None:
        tulip = GlassProfile(depth_mm=110.0, diameters_mm=(60.0, 90.0, 80.0, 65.0))
        assert not ice_fits(tulip, ServingIce.LARGE_CUBE)
        assert ice_fits(tulip, ServingIce.CUBES)

    def test_crushed_ice_fits_any_real_glass(self) -> None:
        assert ice_fits(_cylinder(20.0, 10.0), ServingIce.CRUSHED)


class TestCompatibleIces:
    def test_lists_only_what_fits_in_enum_order(self) -> None:
        rocks = _cylinder(82.0, 70.0)
        assert compatible_ices(rocks) == (
            ServingIce.NONE,
            ServingIce.CUBES,
            ServingIce.LARGE_CUBE,
            ServingIce.CRUSHED,
        )

    def test_no_profile_means_no_restriction(self) -> None:
        assert compatible_ices(None) == tuple(ServingIce)
