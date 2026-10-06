"""Il giudizio dolce / equilibrato / aspro: vale solo per i sour.

La finestra del rapporto zuccheri/acidi descrive il carattere di un sour. Un
Gin Tonic o uno Screwdriver non sono sour: giudicarli con quella finestra
produceva "troppo dolce" su drink perfettamente equilibrati.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from scripts.seed import BAR, CLASSIC_FAMILIES, CLASSICS

from app.domain.balance import (
    SOUR_RATIO_LOWER_BOUND,
    SOUR_RATIO_UPPER_BOUND,
    SourBalance,
    assess_sour_balance,
)
from app.domain.entities import Ingredient, PhysicalProfile, Recipe, RecipeIngredient
from app.domain.enums import RecipeFamily
from app.domain.services.balance_calculator import calculate_balance

#: L'unico sour classico del seed che è dolce per costruzione: la ricetta
#: poggia su un liquore a 40 °Bx. Un giudizio "dolce" qui è la risposta giusta.
SWEET_BY_DESIGN = "Amaretto Sour"


class TestAssessSourBalance:
    def test_a_ratio_inside_the_window_is_balanced(self, daiquiri: Recipe) -> None:
        profile = calculate_balance(daiquiri)

        assert assess_sour_balance(RecipeFamily.SOUR, profile) is SourBalance.BALANCED

    def test_a_sweeter_ratio_is_too_sweet(self, unbalanced_daiquiri: Recipe) -> None:
        # 50/15/35: 21.8 g di zuccheri su 0.9 g di acidi (24), oltre il 12 della finestra.
        profile = calculate_balance(unbalanced_daiquiri)

        assert assess_sour_balance(RecipeFamily.SOUR, profile) is SourBalance.TOO_SWEET

    def test_a_tarter_ratio_is_too_tart(self, daiquiri: Recipe) -> None:
        profile = calculate_balance(daiquiri)
        tart = replace(profile, sugar_acid_ratio=SOUR_RATIO_LOWER_BOUND * 0.9)

        assert assess_sour_balance(RecipeFamily.SOUR, tart) is SourBalance.TOO_TART

    def test_the_window_bounds_are_inclusive(self, daiquiri: Recipe) -> None:
        profile = calculate_balance(daiquiri)

        for edge in (SOUR_RATIO_LOWER_BOUND, SOUR_RATIO_UPPER_BOUND):
            at_edge = replace(profile, sugar_acid_ratio=edge)
            assert assess_sour_balance(RecipeFamily.SOUR, at_edge) is SourBalance.BALANCED

    @pytest.mark.parametrize(
        "family", [None, *[f for f in RecipeFamily if f is not RecipeFamily.SOUR]]
    )
    def test_no_verdict_outside_the_sour_family(
        self, daiquiri: Recipe, family: RecipeFamily | None
    ) -> None:
        """Stessi numeri di un sour, ma il drink non è un sour: nessun giudizio."""
        profile = calculate_balance(daiquiri)

        assert assess_sour_balance(family, profile) is None

    def test_no_verdict_when_there_is_no_ratio(self, gin_tonic: Recipe) -> None:
        profile = calculate_balance(gin_tonic)
        assert profile.sugar_acid_ratio is None

        assert assess_sour_balance(RecipeFamily.SOUR, profile) is None


def _classic_profiles() -> dict[str, tuple[RecipeFamily, Recipe]]:
    """I classici del seed come ricette di dominio, con i dati fisici del seed."""
    catalogue = {
        spec.name: Ingredient(
            id=spec.name,
            name=spec.name,
            category=spec.category,
            physical_profile=PhysicalProfile(
                density_g_ml=spec.density, brix=spec.brix, acidity=spec.acidity, abv=spec.abv
            ),
        )
        for spec in BAR
    }
    classics: dict[str, tuple[RecipeFamily, Recipe]] = {}
    for name, method, ice, _instructions, items in CLASSICS:
        family = CLASSIC_FAMILIES.get(name)
        if family is None:
            continue
        classics[name] = (
            family,
            Recipe(
                id=name,
                name=name,
                dilution_method=method,
                serving_ice=ice,
                family=family,
                ingredients=tuple(
                    RecipeIngredient(ingredient=catalogue[ingredient], volume_ml=volume)
                    for ingredient, volume in items
                ),
            ),
        )
    return classics


class TestWindowIsCalibratedOnTheClassics:
    """La finestra è un fatto empirico: deve riconoscere i sour del seed.

    Non è una verità fisica ma una taratura sui dosaggi tradizionali del
    catalogo: se un classico cade fuori, o la finestra o i dati del seed sono
    sbagliati, e va deciso quale. Il test non fissa i valori del rapporto
    (quelli sono ancorati a mano in `test_balance_calculator.py`), fissa
    l'esito del giudizio.
    """

    def test_every_assessable_sour_classic_is_balanced_except_the_sweet_one(self) -> None:
        verdicts: dict[str, SourBalance] = {}
        for name, (family, recipe) in _classic_profiles().items():
            if family is not RecipeFamily.SOUR:
                continue
            verdict = assess_sour_balance(family, calculate_balance(recipe))
            if verdict is not None:
                verdicts[name] = verdict

        # Senza questa soglia il test passerebbe anche se nessun sour fosse
        # giudicabile.
        assert len(verdicts) >= 18, f"troppi sour senza giudizio: {sorted(verdicts)}"
        assert verdicts.pop(SWEET_BY_DESIGN) is SourBalance.TOO_SWEET
        outliers = {name: v.value for name, v in verdicts.items() if v is not SourBalance.BALANCED}
        assert outliers == {}

    def test_no_classic_outside_the_sour_family_gets_a_verdict(self) -> None:
        judged = [
            name
            for name, (family, recipe) in _classic_profiles().items()
            if family is not RecipeFamily.SOUR
            and assess_sour_balance(family, calculate_balance(recipe)) is not None
        ]
        assert judged == []
