"""Il grafo delle affinità: costruzione, suggerimenti, ponti, comunità."""

from __future__ import annotations

import pytest

from app.application.matching.flavor_graph import (
    MIN_EDGE_WEIGHT,
    FlavorGraph,
    aroma_affinity,
    co_occurrence_weights,
    shared_aroma_descriptors,
)
from app.domain.entities import Ingredient, Recipe, RecipeIngredient
from app.domain.enums import DilutionMethod, IngredientCategory
from app.domain.flavor import FlavorProfile

from .conftest import make_ingredient


def spirit(name: str, **flavor: float) -> Ingredient:
    return make_ingredient(
        name.lower().replace(" ", "-"),
        name,
        IngredientCategory.SPIRIT,
        abv=0.40,
        brix=0.0,
        acidity=0.0,
        density_g_ml=0.95,
        flavor=FlavorProfile.from_descriptors(**flavor),
    )


def recipe(name: str, *ingredients: Ingredient) -> Recipe:
    return Recipe(
        id=name.lower().replace(" ", "-"),
        name=name,
        dilution_method=DilutionMethod.STIRRED,
        ingredients=tuple(
            RecipeIngredient(ingredient=item, volume_ml=30.0) for item in ingredients
        ),
    )


class TestAromaAffinity:
    def test_shared_aromas_score_high(self) -> None:
        smoky = FlavorProfile.from_descriptors(smoke=0.9, earthy=0.6)
        peaty = FlavorProfile.from_descriptors(smoke=0.85, earthy=0.55)
        assert aroma_affinity(smoky, peaty) > 0.95

    def test_disjoint_aromas_score_zero(self) -> None:
        smoky = FlavorProfile.from_descriptors(smoke=0.9)
        floral = FlavorProfile.from_descriptors(floral=0.9)
        assert aroma_affinity(smoky, floral) == pytest.approx(0.0)

    def test_basic_tastes_do_not_create_affinity(self) -> None:
        """Due sciroppi sono entrambi dolcissimi, e questo non significa nulla.

        Se i gusti base entrassero nel calcolo, ogni coppia di sciroppi
        risulterebbe fortemente affine e il grafo si riempirebbe di archi
        che non descrivono alcun abbinamento.
        """
        one_syrup = FlavorProfile.from_descriptors(sweet=1.0)
        other_syrup = FlavorProfile.from_descriptors(sweet=1.0)
        assert aroma_affinity(one_syrup, other_syrup) == pytest.approx(0.0)

    def test_tactile_sensations_do_not_create_affinity(self) -> None:
        """Lo stesso per il calore alcolico, comune a tutti i distillati."""
        first = FlavorProfile.from_descriptors(alcohol_heat=0.7)
        second = FlavorProfile.from_descriptors(alcohol_heat=0.65)
        assert aroma_affinity(first, second) == pytest.approx(0.0)

    def test_a_neutral_profile_has_no_affinity(self) -> None:
        assert aroma_affinity(
            FlavorProfile.neutral(), FlavorProfile.from_descriptors(smoke=0.9)
        ) == pytest.approx(0.0)


class TestSharedDescriptors:
    def test_reports_the_strongest_common_ground_first(self) -> None:
        left = FlavorProfile.from_descriptors(smoke=0.9, woody=0.5, citrus=0.1)
        right = FlavorProfile.from_descriptors(smoke=0.8, woody=0.6, citrus=0.9)
        assert shared_aroma_descriptors(left, right) == ("smoke", "woody", "citrus")

    def test_a_one_sided_aroma_is_not_common_ground(self) -> None:
        """Presente al 90% in uno e assente nell'altro non è terreno comune."""
        left = FlavorProfile.from_descriptors(smoke=0.9)
        right = FlavorProfile.from_descriptors(woody=0.9)
        assert shared_aroma_descriptors(left, right) == ()


class TestCoOccurrence:
    def test_pairs_appearing_together_get_a_weight(self) -> None:
        gin, vermouth, bitter = spirit("Gin", resinous=0.8), spirit("Vermouth"), spirit("Bitter")
        weights = co_occurrence_weights([recipe("Negroni", gin, vermouth, bitter)])

        assert weights[("bitter", "gin")] == pytest.approx(1.0)
        assert len(weights) == 3, "tutte le coppie della ricetta"

    def test_a_ubiquitous_ingredient_is_not_affine_to_everything(self) -> None:
        """La normalizzazione impedisce allo sciroppo semplice di dominare.

        Senza, l'ingrediente presente in ogni ricetta risulterebbe il
        miglior compagno di chiunque — statisticamente vero e praticamente
        inutile.
        """
        syrup = spirit("Syrup", caramel=0.2)
        rum, gin, whisky = spirit("Rum", funky=0.3), spirit("Gin", resinous=0.8), spirit("Whisky")

        weights = co_occurrence_weights(
            [
                recipe("A", syrup, rum),
                recipe("B", syrup, gin),
                recipe("C", syrup, whisky),
                recipe("D", rum, gin),
            ]
        )

        # rum-gin si vedono una volta su due apparizioni ciascuno;
        # syrup-rum una volta su tre apparizioni dello sciroppo.
        assert weights[("gin", "rum")] > weights[("rum", "syrup")]

    def test_no_recipes_means_no_weights(self) -> None:
        assert co_occurrence_weights([]) == {}


class TestGraphConstruction:
    def test_unprofiled_ingredients_stay_out(self) -> None:
        """Un ingrediente senza profilo non è "poco affine": è indescritto.

        Includerlo come nodo isolato lo farebbe apparire valutato e
        scartato, che è un'informazione falsa.
        """
        profiled = spirit("Mezcal", smoke=0.9)
        anonymous = make_ingredient(
            "anon",
            "Anonimo",
            IngredientCategory.SPIRIT,
            abv=0.4,
            brix=0.0,
            acidity=0.0,
            density_g_ml=0.95,
        )

        graph = FlavorGraph.build([profiled, anonymous], [])

        assert {item.id for item in graph.ingredients} == {"mezcal"}

    def test_weak_edges_are_pruned(self) -> None:
        """Un grafo quasi completo non contiene informazione."""
        strong_a = spirit("Mezcal", smoke=0.9, earthy=0.6)
        strong_b = spirit("Islay", smoke=0.85, earthy=0.5)
        unrelated = spirit("Floreale", floral=0.9)

        graph = FlavorGraph.build([strong_a, strong_b, unrelated], [])

        assert graph.stats.edges == 1
        assert graph.stats.nodes == 3

    def test_co_occurrence_creates_an_edge_between_aromatic_strangers(self) -> None:
        """Il segnale delle ricette vede accostamenti che gli aromi non spiegano.

        Gin e bitter non condividono quasi nulla sul piano aromatico, ma
        stanno nello stesso bicchiere da un secolo.
        """
        gin = spirit("Gin", resinous=0.8, pepper=0.3)
        bitter = spirit("Bitter", medicinal=0.9)

        without = FlavorGraph.build([gin, bitter], [])
        with_recipe = FlavorGraph.build([gin, bitter], [recipe("Negroni", gin, bitter)])

        assert without.stats.edges == 0
        assert with_recipe.stats.edges == 1


class TestSuggestions:
    @pytest.fixture
    def bar_graph(self) -> FlavorGraph:
        gin = spirit("Gin", resinous=0.8, citrus=0.4, herbaceous=0.35)
        vermouth = spirit("Vermouth", dried_fruit=0.5, warm_spice=0.4, herbaceous=0.3)
        bitter = spirit("Bitter", citrus=0.5, medicinal=0.4, floral=0.2)
        chartreuse = spirit("Chartreuse", herbaceous=0.95, mint=0.5, anise=0.4)
        mezcal = spirit("Mezcal", smoke=0.9, earthy=0.6)

        return FlavorGraph.build(
            [gin, vermouth, bitter, chartreuse, mezcal],
            [recipe("Negroni", gin, vermouth, bitter)],
        )

    def test_suggests_something_related_to_the_seeds(self, bar_graph: FlavorGraph) -> None:
        suggestions = bar_graph.suggest(["gin"], limit=3)

        assert suggestions
        assert all(item.ingredient.id != "gin" for item in suggestions)
        assert all(item.rationale for item in suggestions)

    def test_never_suggests_what_is_already_in_the_glass(self, bar_graph: FlavorGraph) -> None:
        seeds = ["gin", "vermouth", "bitter"]
        suggested = {item.ingredient.id for item in bar_graph.suggest(seeds, limit=10)}
        assert suggested.isdisjoint(seeds)

    def test_a_near_duplicate_of_a_seed_is_filtered_out(self) -> None:
        """Suggerire il limone a chi ha già il lime è il fallimento classico.

        I due hanno profili quasi identici: l'arco fra loro è fortissimo e
        senza il filtro sarebbero il primo suggerimento l'uno per l'altro.
        """
        lime = spirit("Lime", citrus=0.90, herbaceous=0.20)
        lemon = spirit("Limone", citrus=0.91, herbaceous=0.20)
        gin = spirit("Gin", resinous=0.8, citrus=0.4)

        graph = FlavorGraph.build([lime, lemon, gin], [])
        suggested = {item.ingredient.id for item in graph.suggest(["lime"], limit=5)}

        assert "limone" not in suggested

    def test_an_unknown_seed_yields_nothing(self, bar_graph: FlavorGraph) -> None:
        assert bar_graph.suggest(["non-esiste"], limit=5) == []

    def test_an_empty_graph_yields_nothing(self) -> None:
        graph = FlavorGraph.build([spirit("Solo", smoke=0.9)], [])
        assert graph.suggest(["solo"], limit=5) == []

    def test_the_rationale_names_the_source_of_the_affinity(self, bar_graph: FlavorGraph) -> None:
        suggestions = bar_graph.suggest(["gin", "vermouth"], limit=3)
        assert any(
            "ricette esistenti" in item.rationale or "profilo aromatico" in item.rationale
            for item in suggestions
        )


class TestBridge:
    @pytest.fixture
    def chain_graph(self) -> FlavorGraph:
        # Catena deliberata: A-B condividono il fumo, B-C il legno,
        # C-D la vaniglia. A e D non hanno nulla in comune.
        first = spirit("Uno", smoke=0.9)
        second = spirit("Due", smoke=0.85, woody=0.6)
        third = spirit("Tre", woody=0.6, vanilla=0.7)
        fourth = spirit("Quattro", vanilla=0.75)
        return FlavorGraph.build([first, second, third, fourth], [])

    def test_finds_the_intermediate_ingredients(self, chain_graph: FlavorGraph) -> None:
        bridge = chain_graph.bridge("uno", "quattro")

        assert bridge is not None
        assert [item.id for item in bridge.path] == ["uno", "due", "tre", "quattro"]

    def test_strength_is_the_product_of_the_affinities(self, chain_graph: FlavorGraph) -> None:
        bridge = chain_graph.bridge("uno", "quattro")

        assert bridge is not None
        assert 0.0 < bridge.strength <= 1.0
        # Tre archi deboli in catena: il legame complessivo è molto più
        # debole di ciascun anello.
        assert bridge.strength < MIN_EDGE_WEIGHT

    def test_neighbours_bridge_in_one_step(self, chain_graph: FlavorGraph) -> None:
        bridge = chain_graph.bridge("uno", "due")

        assert bridge is not None
        assert len(bridge.path) == 2

    def test_returns_none_when_the_two_are_not_connected(self) -> None:
        island = spirit("Isola", smoke=0.9)
        other = spirit("Altra Isola", floral=0.9)
        graph = FlavorGraph.build([island, other], [])

        assert graph.bridge("isola", "altra-isola") is None

    def test_returns_none_for_an_unknown_ingredient(self, chain_graph: FlavorGraph) -> None:
        assert chain_graph.bridge("uno", "non-esiste") is None

    def test_the_query_does_not_mutate_the_graph(self, chain_graph: FlavorGraph) -> None:
        """Il grafo può arrivare dalla cache: una lettura non deve alterarlo."""
        before = chain_graph.stats
        chain_graph.bridge("uno", "quattro")
        assert chain_graph.stats == before


class TestCommunities:
    def test_families_emerge_from_the_data(self) -> None:
        """Due gruppi aromatici separati devono risultare due comunità."""
        smoky_one = spirit("Fumo Uno", smoke=0.9, earthy=0.6)
        smoky_two = spirit("Fumo Due", smoke=0.85, earthy=0.55)
        floral_one = spirit("Fiore Uno", floral=0.9, citrus=0.4)
        floral_two = spirit("Fiore Due", floral=0.85, citrus=0.45)

        graph = FlavorGraph.build([smoky_one, smoky_two, floral_one, floral_two], [])
        communities = graph.communities()

        assert len(communities) == 2
        assert any({"fumo-uno", "fumo-due"} <= group for group in communities)

    def test_an_edgeless_graph_has_no_communities(self) -> None:
        assert FlavorGraph.build([spirit("Solo", smoke=0.9)], []).communities() == []


class TestSerialization:
    def test_a_round_trip_preserves_the_graph(self) -> None:
        gin = spirit("Gin", resinous=0.8, citrus=0.4)
        vermouth = spirit("Vermouth", dried_fruit=0.5, herbaceous=0.3)
        bitter = spirit("Bitter", citrus=0.5, medicinal=0.4)
        ingredients = [gin, vermouth, bitter]

        original = FlavorGraph.build(ingredients, [recipe("Negroni", gin, vermouth, bitter)])
        restored = FlavorGraph.from_payload(original.to_payload(), ingredients)

        assert restored is not None
        assert restored.stats == original.stats
        assert restored.suggest(["gin"], limit=3) == original.suggest(["gin"], limit=3)

    def test_a_corrupt_payload_is_reported_not_raised(self) -> None:
        """Una cache corrotta non deve far fallire una richiesta."""
        assert FlavorGraph.from_payload("{non json", [spirit("Gin", resinous=0.8)]) is None
        assert FlavorGraph.from_payload('{"altro": 1}', [spirit("Gin", resinous=0.8)]) is None

    def test_edges_towards_ingredients_no_longer_available_are_dropped(self) -> None:
        """Il grafo ricostruito deve riflettere la dispensa di adesso.

        Un ingrediente disattivato dopo la scrittura in cache non compare
        più fra quelli caricati, e i suoi archi vanno ignorati invece che
        ricreati.
        """
        first = spirit("Fumo Uno", smoke=0.9, earthy=0.6)
        second = spirit("Fumo Due", smoke=0.85, earthy=0.55)
        payload = FlavorGraph.build([first, second], []).to_payload()

        restored = FlavorGraph.from_payload(payload, [first])

        assert restored is not None
        assert restored.stats.nodes == 1
        assert restored.stats.edges == 0
