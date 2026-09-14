"""La tassonomia organolettica e la similarità del coseno."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.errors import InvalidFlavorProfileError
from app.domain.flavor import (
    AROMA_DESCRIPTORS,
    BASIC_TASTE_DESCRIPTORS,
    FLAVOR_DESCRIPTORS,
    FLAVOR_VECTOR_DIMENSION,
    TACTILE_DESCRIPTORS,
    FlavorProfile,
)


class TestTaxonomy:
    def test_the_three_families_compose_the_whole_vector(self) -> None:
        assert (
            len(BASIC_TASTE_DESCRIPTORS) + len(TACTILE_DESCRIPTORS) + len(AROMA_DESCRIPTORS)
            == FLAVOR_VECTOR_DIMENSION
        )

    def test_descriptor_names_are_unique(self) -> None:
        """I nomi sono la chiave di `from_descriptors`: un duplicato
        renderebbe due posizioni del vettore indistinguibili."""
        assert len(set(FLAVOR_DESCRIPTORS)) == len(FLAVOR_DESCRIPTORS)

    def test_dimension_matches_the_declared_contract(self) -> None:
        """La dimensione è parte dello schema del database.

        La colonna è dichiarata `vector(32)`: cambiare questo numero senza
        una migrazione romperebbe ogni scrittura, e questo test lo rende
        impossibile da fare per distrazione.
        """
        assert FLAVOR_VECTOR_DIMENSION == 32


class TestConstruction:
    def test_from_descriptors_places_values_at_the_right_index(self) -> None:
        profile = FlavorProfile.from_descriptors(sour=0.9, citrus=0.85)
        as_dict = profile.as_dict()

        assert as_dict["sour"] == 0.9
        assert as_dict["citrus"] == 0.85
        assert as_dict["smoke"] == 0.0

    def test_from_descriptors_rejects_a_typo(self) -> None:
        """In un vocabolario di 32 termini il refuso è il rischio reale.

        Ignorarlo in silenzio produrrebbe un ingrediente il cui profilo è
        vuoto senza che nessuno se ne accorga finché il matcher non
        restituisce risultati insensati.
        """
        with pytest.raises(InvalidFlavorProfileError, match="citrusy"):
            FlavorProfile.from_descriptors(citrusy=0.9)

    def test_rejects_a_vector_of_the_wrong_dimension(self) -> None:
        with pytest.raises(InvalidFlavorProfileError, match="32"):
            FlavorProfile(components=(0.1, 0.2, 0.3))

    @pytest.mark.parametrize("value", [-0.01, 1.01])
    def test_rejects_intensities_outside_the_unit_interval(self, value: float) -> None:
        with pytest.raises(InvalidFlavorProfileError):
            FlavorProfile.from_descriptors(sweet=value)

    def test_neutral_profile_is_all_zeros(self) -> None:
        assert set(FlavorProfile.neutral().as_dict().values()) == {0.0}


class TestDominantDescriptors:
    def test_returns_the_strongest_first(self) -> None:
        profile = FlavorProfile.from_descriptors(bitter=0.95, sweet=0.5, citrus=0.7)
        assert [name for name, _ in profile.dominant()] == ["bitter", "citrus", "sweet"]

    def test_omits_absent_descriptors(self) -> None:
        profile = FlavorProfile.from_descriptors(sweet=1.0)
        assert profile.dominant() == (("sweet", 1.0),)

    def test_honours_the_limit(self) -> None:
        profile = FlavorProfile.from_descriptors(
            sweet=0.9, sour=0.8, bitter=0.7, citrus=0.6, smoke=0.5, woody=0.4
        )
        assert len(profile.dominant(limit=3)) == 3


class TestCosineSimilarity:
    def test_identical_profiles_are_maximally_similar(self) -> None:
        profile = FlavorProfile.from_descriptors(sour=0.9, citrus=0.85)
        assert profile.cosine_similarity(profile) == pytest.approx(1.0)

    def test_disjoint_profiles_share_nothing(self) -> None:
        citrus = FlavorProfile.from_descriptors(sour=0.9, citrus=0.9)
        smoky = FlavorProfile.from_descriptors(smoke=0.9, roasted=0.8)
        assert citrus.cosine_similarity(smoky) == pytest.approx(0.0)

    def test_similarity_ignores_intensity_and_keeps_direction(self) -> None:
        """Due profili proporzionali descrivono lo stesso carattere.

        È la proprietà che serve alla sostituzione: un lime "compilato
        forte" e uno "compilato timido" restano lo stesso ingrediente dal
        punto di vista organolettico.
        """
        strong = FlavorProfile.from_descriptors(sour=0.9, citrus=0.9)
        faint = FlavorProfile.from_descriptors(sour=0.3, citrus=0.3)
        assert strong.cosine_similarity(faint) == pytest.approx(1.0)

    def test_a_neutral_profile_has_no_direction(self) -> None:
        profile = FlavorProfile.from_descriptors(sweet=1.0)
        assert profile.cosine_similarity(FlavorProfile.neutral()) == 0.0

    def test_closer_ingredients_score_higher(self) -> None:
        """Lime e limone si somigliano più di lime e mezcal."""
        lime = FlavorProfile.from_descriptors(sour=0.95, citrus=0.9, herbaceous=0.2)
        lemon = FlavorProfile.from_descriptors(sour=0.9, citrus=0.95, floral=0.15)
        mezcal = FlavorProfile.from_descriptors(smoke=0.9, earthy=0.6, alcohol_heat=0.7)

        assert lime.cosine_similarity(lemon) > lime.cosine_similarity(mezcal)

    @given(
        first=st.lists(
            st.floats(0.0, 1.0, allow_nan=False),
            min_size=FLAVOR_VECTOR_DIMENSION,
            max_size=FLAVOR_VECTOR_DIMENSION,
        ),
        second=st.lists(
            st.floats(0.0, 1.0, allow_nan=False),
            min_size=FLAVOR_VECTOR_DIMENSION,
            max_size=FLAVOR_VECTOR_DIMENSION,
        ),
    )
    def test_similarity_is_bounded_and_symmetric(
        self, first: list[float], second: list[float]
    ) -> None:
        """Le componenti sono non negative, quindi il coseno vive in [0, 1]."""
        left = FlavorProfile(components=tuple(first))
        right = FlavorProfile(components=tuple(second))

        similarity = left.cosine_similarity(right)
        assert 0.0 <= similarity <= 1.0
        assert similarity == pytest.approx(right.cosine_similarity(left))
