"""Semantica della sostituzione: somigliare non basta, bisogna comportarsi uguale."""

from __future__ import annotations

import pytest

from app.domain.entities import Ingredient, PhysicalProfile
from app.domain.enums import IngredientCategory
from app.domain.flavor import FlavorProfile
from app.domain.services.substitution import (
    physical_compatibility,
    physical_distance,
    score_substitution,
    substitution_warnings,
)

from .conftest import make_ingredient


def profile(abv: float, brix: float, acidity: float, density: float = 1.0) -> PhysicalProfile:
    return PhysicalProfile(density_g_ml=density, brix=brix, acidity=acidity, abv=abv)


class TestPhysicalDistance:
    def test_identical_profiles_are_at_zero_distance(self) -> None:
        same = profile(0.40, 10.0, 1.0)
        assert physical_distance(same, same) == pytest.approx(0.0)
        assert physical_compatibility(same, same) == pytest.approx(1.0)

    def test_each_axis_is_normalised_by_its_own_scale(self) -> None:
        """Uno scarto di una scala pesa uguale su ogni asse.

        È il punto della normalizzazione: 10 punti di ABV, 10 °Bx e 1 punto
        di acidità sono scarti confrontabili, e senza le scale l'asse del
        Brix — che vive fra 0 e 100 — dominerebbe tutti gli altri.
        """
        base = profile(0.20, 20.0, 2.0)
        by_abv = physical_distance(base, profile(0.30, 20.0, 2.0))
        by_brix = physical_distance(base, profile(0.20, 30.0, 2.0))
        by_acidity = physical_distance(base, profile(0.20, 20.0, 3.0))

        assert by_abv == pytest.approx(1.0)
        assert by_brix == pytest.approx(1.0)
        assert by_acidity == pytest.approx(1.0)

    def test_density_is_deliberately_ignored(self) -> None:
        """La densità è quasi interamente determinata dal Brix.

        Includerla significherebbe pesare due volte lo stesso fatto.
        """
        light = profile(0.0, 50.0, 0.0, density=1.05)
        heavy = profile(0.0, 50.0, 0.0, density=1.45)
        assert physical_distance(light, heavy) == pytest.approx(0.0)

    def test_compatibility_halves_at_one_scale_of_distance(self) -> None:
        base = profile(0.20, 20.0, 2.0)
        assert physical_compatibility(base, profile(0.30, 20.0, 2.0)) == pytest.approx(0.5)

    def test_compatibility_stays_within_the_unit_interval(self) -> None:
        near_opposite = physical_compatibility(profile(1.0, 0.0, 0.0), profile(0.0, 100.0, 10.0))
        assert 0.0 < near_opposite < 0.1


class TestWarnings:
    def test_a_close_substitute_raises_nothing(self) -> None:
        assert substitution_warnings(profile(0.0, 7.5, 6.0), profile(0.0, 8.0, 5.5)) == ()

    def test_a_missing_acid_is_reported_with_what_to_do(self) -> None:
        notes = substitution_warnings(profile(0.0, 7.5, 6.0), profile(0.0, 9.0, 2.0))
        assert any("acidità" in note and "reintegrare" in note for note in notes)

    def test_an_alcoholic_substitute_for_a_juice_is_reported(self) -> None:
        notes = substitution_warnings(profile(0.0, 7.5, 6.0), profile(0.40, 25.0, 0.0))
        assert any("ABV" in note for note in notes)
        assert any("°Bx" in note for note in notes)


class TestScoring:
    def test_the_two_axes_multiply_instead_of_averaging(self) -> None:
        """Un candidato assurdo su un asse non si salva eccellendo sull'altro.

        Con una media, uno sciroppo al lime (aroma quasi identico, fisica
        opposta) passerebbe con 0.5 e comparirebbe fra i primi risultati.
        """
        lime = make_ingredient(
            "lime",
            "Succo di Lime",
            IngredientCategory.JUICE,
            abv=0.0,
            brix=7.5,
            acidity=6.0,
            density_g_ml=1.03,
            flavor=FlavorProfile.from_descriptors(sour=0.95, citrus=0.9),
        )
        lime_syrup = make_ingredient(
            "lime-syrup",
            "Sciroppo al Lime",
            IngredientCategory.SYRUP,
            abv=0.0,
            brix=55.0,
            acidity=0.5,
            density_g_ml=1.26,
            flavor=FlavorProfile.from_descriptors(sour=0.95, citrus=0.9),
        )

        score = score_substitution(lime, lime_syrup)

        assert score.flavor_similarity == pytest.approx(1.0), "stesso profilo aromatico"
        assert score.physical_compatibility < 0.2, "comportamento fisico opposto"
        assert score.overall < 0.2
        assert score.overall == pytest.approx(
            score.flavor_similarity * score.physical_compatibility
        )

    def test_lemon_beats_grapefruit_as_a_lime_substitute(self, lime_juice: Ingredient) -> None:
        """Il caso reale: entrambi agrumi, ma solo uno ha l'acidità giusta."""
        lemon = make_ingredient(
            "lemon",
            "Succo di Limone",
            IngredientCategory.JUICE,
            abv=0.0,
            brix=2.5,
            acidity=5.5,
            density_g_ml=1.02,
            flavor=FlavorProfile.from_descriptors(sour=0.95, citrus=0.95, floral=0.15),
        )
        grapefruit = make_ingredient(
            "grapefruit",
            "Succo di Pompelmo",
            IngredientCategory.JUICE,
            abv=0.0,
            brix=9.0,
            acidity=2.0,
            density_g_ml=1.04,
            flavor=FlavorProfile.from_descriptors(sour=0.6, bitter=0.4, citrus=0.85),
        )

        assert (
            score_substitution(lime_juice, lemon).overall
            > score_substitution(lime_juice, grapefruit).overall
        )

    def test_an_unprofiled_candidate_scores_zero_on_flavour(self, lime_juice: Ingredient) -> None:
        anonymous = make_ingredient(
            "anon",
            "Distillato Anonimo",
            IngredientCategory.SPIRIT,
            abv=0.40,
            brix=0.0,
            acidity=0.0,
            density_g_ml=0.95,
        )
        assert score_substitution(lime_juice, anonymous).flavor_similarity == 0.0
