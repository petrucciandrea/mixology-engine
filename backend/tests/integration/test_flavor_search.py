"""Ricerca vettoriale su pgvector, contro un PostgreSQL reale."""

from __future__ import annotations

import pytest

from app.domain.enums import IngredientCategory
from app.domain.flavor import FlavorProfile
from app.domain.matching import FlavorSearchRepository
from app.domain.repositories import IngredientRepository, UnitOfWork

from .conftest import make_ingredient

pytestmark = pytest.mark.integration


LIME = FlavorProfile.from_descriptors(sour=0.95, citrus=0.9, herbaceous=0.2)
LEMON = FlavorProfile.from_descriptors(sour=0.9, citrus=0.95, floral=0.15)
MEZCAL = FlavorProfile.from_descriptors(smoke=0.9, earthy=0.6, alcohol_heat=0.7)


class TestFindSimilar:
    async def test_the_closest_profile_comes_first(
        self,
        flavor_search: FlavorSearchRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        lemon = make_ingredient("Limone", IngredientCategory.JUICE, flavor=LEMON)
        mezcal = make_ingredient("Mezcal", IngredientCategory.SPIRIT, flavor=MEZCAL)
        for ingredient in (lemon, mezcal):
            await ingredient_repository.add(ingredient)
        await unit_of_work.commit()

        # Il limite è volutamente alto: il database di sviluppo contiene la
        # dispensa del seed, e con una finestra stretta il mezcal — che è il
        # termine di paragone lontano — resterebbe fuori dai risultati per
        # ragioni che non hanno nulla a che vedere con ciò che si verifica.
        hits = await flavor_search.find_similar(LIME, limit=500)
        ranked = [hit.ingredient.id for hit in hits]

        assert ranked.index(lemon.id) < ranked.index(mezcal.id)

    async def test_pgvector_agrees_with_the_domain_implementation(
        self,
        flavor_search: FlavorSearchRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        """Il punteggio del database deve coincidere con quello del dominio.

        È il test più importante del modulo: `FlavorProfile.cosine_similarity`
        resta l'implementazione di riferimento, leggibile e testata in
        isolamento, mentre pgvector è un'ottimizzazione — e un'ottimizzazione
        che restituisce numeri diversi dall'originale è un bug, non
        un'ottimizzazione.

        La tolleranza è larga perché la colonna `vector` è a precisione
        singola: la differenza attesa è dell'ordine di 10⁻⁷.
        """
        lemon = make_ingredient("Limone", IngredientCategory.JUICE, flavor=LEMON)
        await ingredient_repository.add(lemon)
        await unit_of_work.commit()

        hits = await flavor_search.find_similar(LIME, limit=50)
        found = next(hit for hit in hits if hit.ingredient.id == lemon.id)

        assert found.similarity == pytest.approx(LIME.cosine_similarity(LEMON), abs=1e-5)

    async def test_similarity_stays_within_the_unit_interval(
        self,
        flavor_search: FlavorSearchRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        """Un profilo identico non deve produrre 1.0000001 per arrotondamento."""
        twin = make_ingredient("Gemello", IngredientCategory.JUICE, flavor=LIME)
        await ingredient_repository.add(twin)
        await unit_of_work.commit()

        hits = await flavor_search.find_similar(LIME, limit=50)
        found = next(hit for hit in hits if hit.ingredient.id == twin.id)

        assert found.similarity == pytest.approx(1.0, abs=1e-5)
        assert 0.0 <= found.similarity <= 1.0

    async def test_unprofiled_ingredients_never_appear(
        self,
        flavor_search: FlavorSearchRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        """Senza vettore non è "lontano": è non confrontabile."""
        anonymous = make_ingredient("Anonimo", IngredientCategory.SPIRIT, flavor=None)
        await ingredient_repository.add(anonymous)
        await unit_of_work.commit()

        hits = await flavor_search.find_similar(LIME, limit=200)

        assert anonymous.id not in {hit.ingredient.id for hit in hits}

    async def test_excluded_ids_are_left_out(
        self,
        flavor_search: FlavorSearchRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        """Serve a non proporre un ingrediente come sostituto di se stesso."""
        twin = make_ingredient("Gemello", IngredientCategory.JUICE, flavor=LIME)
        await ingredient_repository.add(twin)
        await unit_of_work.commit()

        hits = await flavor_search.find_similar(LIME, limit=50, exclude_ids=(twin.id,))

        assert twin.id not in {hit.ingredient.id for hit in hits}

    async def test_the_category_filter_narrows_the_search(
        self,
        flavor_search: FlavorSearchRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        juice = make_ingredient("Agrume", IngredientCategory.JUICE, flavor=LEMON)
        liqueur = make_ingredient(
            "Liquore d'Agrumi", IngredientCategory.LIQUEUR, abv=0.4, brix=25.0, flavor=LEMON
        )
        for ingredient in (juice, liqueur):
            await ingredient_repository.add(ingredient)
        await unit_of_work.commit()

        hits = await flavor_search.find_similar(LIME, limit=200, category=IngredientCategory.JUICE)
        found = {hit.ingredient.id for hit in hits}

        assert juice.id in found
        assert liqueur.id not in found

    async def test_deactivated_ingredients_are_excluded_by_default(
        self,
        flavor_search: FlavorSearchRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        from dataclasses import replace

        retired = make_ingredient("Fuori Listino", IngredientCategory.JUICE, flavor=LIME)
        await ingredient_repository.add(retired)
        await ingredient_repository.save(replace(retired, is_active=False))
        await unit_of_work.commit()

        active = await flavor_search.find_similar(LIME, limit=200)
        everything = await flavor_search.find_similar(LIME, limit=200, active_only=False)

        assert retired.id not in {hit.ingredient.id for hit in active}
        assert retired.id in {hit.ingredient.id for hit in everything}

    async def test_the_limit_is_applied_by_the_database(
        self,
        flavor_search: FlavorSearchRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        for index in range(5):
            await ingredient_repository.add(
                make_ingredient(f"Agrume {index}", IngredientCategory.JUICE, flavor=LEMON)
            )
        await unit_of_work.commit()

        assert len(await flavor_search.find_similar(LIME, limit=3)) == 3


class TestListProfiled:
    async def test_returns_only_ingredients_with_a_profile(
        self,
        flavor_search: FlavorSearchRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        profiled = make_ingredient("Profilato", IngredientCategory.JUICE, flavor=LIME)
        anonymous = make_ingredient("Anonimo", IngredientCategory.SPIRIT, flavor=None)
        for ingredient in (profiled, anonymous):
            await ingredient_repository.add(ingredient)
        await unit_of_work.commit()

        found = {item.id for item in await flavor_search.list_profiled()}

        assert profiled.id in found
        assert anonymous.id not in found

    async def test_the_profile_survives_the_round_trip(
        self,
        flavor_search: FlavorSearchRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        ingredient = make_ingredient("Mezcal", IngredientCategory.SPIRIT, flavor=MEZCAL)
        await ingredient_repository.add(ingredient)
        await unit_of_work.commit()

        loaded = next(
            item for item in await flavor_search.list_profiled() if item.id == ingredient.id
        )

        assert loaded.flavor_profile == MEZCAL


class TestGraphFingerprint:
    async def test_it_changes_when_a_profiled_ingredient_is_added(
        self,
        flavor_search: FlavorSearchRepository,
        ingredient_repository: IngredientRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        """È ciò che rende automatica l'invalidazione della cache.

        Se l'impronta non cambiasse, il grafo in cache resterebbe valido
        per la sua TTL anche dopo l'ingresso di un ingrediente nuovo, che
        quindi non comparirebbe in nessun suggerimento.
        """
        before = await flavor_search.graph_fingerprint()

        await ingredient_repository.add(
            make_ingredient("Novità", IngredientCategory.SPIRIT, flavor=MEZCAL)
        )
        await unit_of_work.commit()

        assert await flavor_search.graph_fingerprint() != before

    async def test_it_is_stable_when_nothing_changes(
        self, flavor_search: FlavorSearchRepository
    ) -> None:
        """Altrimenti la cache non verrebbe mai usata."""
        assert await flavor_search.graph_fingerprint() == (await flavor_search.graph_fingerprint())
