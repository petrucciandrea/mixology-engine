"""Casi d'uso del matcher: sostituzioni, abbinamenti, ponti aromatici."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Final

from app.application.matching.flavor_graph import FlavorGraph, GraphStats
from app.domain.entities import Ingredient
from app.domain.errors import EntityNotFoundError
from app.domain.matching import (
    FlavorBridge,
    FlavorSearchRepository,
    GraphSnapshotCache,
    PairingSuggestion,
    SubstitutionCandidate,
)
from app.domain.repositories import IngredientRepository, RecipeRepository
from app.domain.services.substitution import score_substitution

#: Quanti candidati chiedere a pgvector per ogni risultato richiesto.
#:
#: La ricerca vettoriale ordina per sola similarità organolettica, mentre il
#: punteggio finale include anche la compatibilità fisica: il riordino può
#: promuovere un candidato che era settimo e retrocedere il secondo. Senza
#: margine si perderebbero proprio i sostituti buoni ma non primi per aroma.
#: Quattro volte è un compromesso: abbastanza da assorbire il riordino,
#: abbastanza poco da restare una singola query indicizzata.
OVERFETCH_FACTOR: Final[int] = 4

#: Durata della voce di cache del grafo.
#:
#: L'impronta invalida già la cache quando cambiano il numero di ingredienti
#: profilati, le ricette o la data di ultima modifica. Il TTL copre il caso
#: residuo — una modifica che lascia l'impronta invariata — e tiene la cache
#: piccola. Cinque minuti: un grafo vecchio di cinque minuti non ha mai
#: fatto danni a nessuno.
GRAPH_CACHE_TTL_SECONDS: Final[int] = 300

_GRAPH_CACHE_PREFIX: Final[str] = "flavor-graph:v1:"


@dataclass(frozen=True, slots=True)
class GraphOverview:
    """Fotografia del grafo: struttura e famiglie emerse."""

    stats: GraphStats
    communities: tuple[tuple[Ingredient, ...], ...]


class FlavorGraphProvider:
    """Costruisce il grafo, passando dalla cache quando può.

    La costruzione è O(n²) sulle coppie di ingredienti profilati ed è
    CPU-bound: con la dispensa di un bar è questione di millisecondi, ma
    resta lavoro sincrono, e come il solver va tenuto fuori dall'event loop
    (ADR-0002).
    """

    def __init__(
        self,
        flavor_search: FlavorSearchRepository,
        recipes: RecipeRepository,
        cache: GraphSnapshotCache,
    ) -> None:
        self._flavor_search = flavor_search
        self._recipes = recipes
        self._cache = cache

    async def get(self) -> FlavorGraph:
        ingredients = await self._flavor_search.list_profiled()
        fingerprint = await self._flavor_search.graph_fingerprint()
        key = f"{_GRAPH_CACHE_PREFIX}{fingerprint}"

        cached = await self._cache.get(key)
        if cached is not None:
            graph = FlavorGraph.from_payload(cached, ingredients)
            if graph is not None:
                return graph
            # Payload illeggibile: si ricostruisce e si riscrive, invece di
            # far fallire una richiesta per colpa della cache.

        recipes = await self._recipes.list(limit=1000)
        graph = await asyncio.to_thread(FlavorGraph.build, ingredients, recipes)
        await self._cache.set(key, graph.to_payload(), GRAPH_CACHE_TTL_SECONDS)
        return graph


class FindSubstitutesUseCase:
    """Trova sostituti per un ingrediente, ordinati per utilità reale.

    Due fasi, con divisione del lavoro netta: pgvector fa la ricerca per
    prossimità organolettica sull'indice HNSW — l'unica cosa che sa fare
    bene e che in Python costerebbe una scansione completa — e il dominio
    riordina i candidati tenendo conto della compatibilità fisica, che il
    database non conosce.
    """

    def __init__(
        self, ingredients: IngredientRepository, flavor_search: FlavorSearchRepository
    ) -> None:
        self._ingredients = ingredients
        self._flavor_search = flavor_search

    async def execute(
        self,
        ingredient_id: str,
        *,
        limit: int = 5,
        same_category_only: bool = False,
    ) -> list[SubstitutionCandidate]:
        original = await self._ingredients.get(ingredient_id)
        if original is None:
            raise EntityNotFoundError("Ingredient", ingredient_id)
        if original.flavor_profile is None:
            # Non è un errore: è un ingrediente non ancora profilato, e la
            # risposta onesta è "non lo so", cioè nessun candidato — non una
            # lista di sostituti scelti a caso.
            return []

        hits = await self._flavor_search.find_similar(
            original.flavor_profile,
            limit=limit * OVERFETCH_FACTOR,
            exclude_ids=(ingredient_id,),
            category=original.category if same_category_only else None,
        )

        candidates = [
            SubstitutionCandidate(
                ingredient=hit.ingredient,
                score=score_substitution(original, hit.ingredient),
            )
            for hit in hits
        ]
        candidates.sort(key=lambda candidate: -candidate.overall)
        return candidates[:limit]


class SuggestPairingsUseCase:
    """Suggerisce cosa aggiungere a una ricetta in costruzione."""

    def __init__(self, provider: FlavorGraphProvider) -> None:
        self._provider = provider

    async def execute(
        self, ingredient_ids: list[str], *, limit: int = 5
    ) -> list[PairingSuggestion]:
        graph = await self._provider.get()
        return graph.suggest(ingredient_ids, limit=limit)


class FindFlavorBridgeUseCase:
    """Trova gli ingredienti che collegano due estremi lontani."""

    def __init__(self, ingredients: IngredientRepository, provider: FlavorGraphProvider) -> None:
        self._ingredients = ingredients
        self._provider = provider

    async def execute(self, source_id: str, target_id: str) -> FlavorBridge | None:
        for ingredient_id in (source_id, target_id):
            if await self._ingredients.get(ingredient_id) is None:
                raise EntityNotFoundError("Ingredient", ingredient_id)

        graph = await self._provider.get()
        return graph.bridge(source_id, target_id)


class DescribeFlavorGraphUseCase:
    """Struttura del grafo e famiglie di ingredienti emerse dai dati."""

    def __init__(self, provider: FlavorGraphProvider) -> None:
        self._provider = provider

    async def execute(self) -> GraphOverview:
        graph = await self._provider.get()
        communities = graph.communities()
        by_id = {ingredient.id: ingredient for ingredient in graph.ingredients}

        return GraphOverview(
            stats=graph.stats,
            communities=tuple(
                tuple(
                    sorted(
                        (by_id[node] for node in group if node in by_id),
                        key=lambda ingredient: ingredient.name,
                    )
                )
                # Le famiglie si presentano dalla più numerosa: è l'ordine in
                # cui chi legge si aspetta di trovare la struttura portante
                # della propria dispensa.
                for group in sorted(communities, key=len, reverse=True)
            ),
        )
