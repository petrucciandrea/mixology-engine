"""Grafo delle affinità fra ingredienti (NetworkX).

Il grafo è indiretto e pesato: i nodi sono ingredienti, il peso di un arco
misura quanto due ingredienti stiano bene insieme. Due segnali indipendenti
lo compongono.

**Co-occorrenza nelle ricette.** Se gin e vermouth rosso compaiono insieme
in molte ricette, l'accostamento è già stato validato da chi le ha scritte.
È il segnale più affidabile ma anche il più conservativo: conosce solo ciò
che esiste già, e da solo non proporrebbe mai nulla di nuovo.

**Aromi condivisi.** L'ipotesi del *food pairing* sostiene che due
ingredienti si accostino bene quando condividono composti aromatici. Qui la
si applica al sottovettore delle 23 famiglie aromatiche: il coseno su quel
blocco misura quanta parte del carattere olfattivo i due condividono. È il
segnale che propone accostamenti mai visti in una ricetta.

Perché un grafo e non una semplice classifica: le domande interessanti sono
*relazionali*. "Cosa aggiungo a questi tre ingredienti insieme" è una
propagazione sull'intera rete, non la somma di tre classifiche
indipendenti — ed è esattamente ciò che calcola il PageRank personalizzato.
"Come arrivo dal mezcal alla fragola" è un cammino, e non ha nessuna
formulazione sensata fuori da un grafo.

Nota importante: **affinità non è similarità**. Due succhi di agrume
condividono quasi tutti gli aromi e avrebbero quindi un arco fortissimo, ma
metterli insieme nello stesso drink è ridondante, non complementare. Il
suggeritore scarta esplicitamente i candidati troppo simili a ciò che è già
nel bicchiere (`REDUNDANCY_THRESHOLD`).
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Final

import networkx as nx

from app.domain.entities import Ingredient, Recipe
from app.domain.flavor import AROMA_DESCRIPTORS, FLAVOR_DESCRIPTORS, FlavorProfile
from app.domain.matching import FlavorBridge, PairingSuggestion

#: Peso dei due segnali nella somma che forma l'arco. La co-occorrenza pesa
#: di più perché è evidenza diretta: qualcuno ha davvero messo quei due
#: ingredienti nello stesso bicchiere e la ricetta è sopravvissuta.
#: Gli aromi condivisi sono un'inferenza, e servono soprattutto dove la
#: co-occorrenza è muta — cioè sugli accostamenti che nessuno ha ancora
#: provato, che sono poi quelli per cui si usa uno strumento del genere.
CO_OCCURRENCE_WEIGHT: Final[float] = 0.6
AROMA_WEIGHT: Final[float] = 0.4

#: Archi più deboli di così vengono scartati. Senza potatura il grafo
#: diventa quasi completo — quasi ogni coppia condivide *qualche* aroma — e
#: un grafo completo non contiene informazione: ogni cammino è diretto e il
#: PageRank tende alla distribuzione uniforme.
MIN_EDGE_WEIGHT: Final[float] = 0.08

#: Sopra questa similarità complessiva un candidato è un doppione di ciò che
#: è già nella ricetta, non un'aggiunta. Suggerire il limone a chi ha già il
#: lime è il modo classico in cui questi sistemi falliscono.
REDUNDANCY_THRESHOLD: Final[float] = 0.90

#: Quanti descrittori citare nella motivazione di un suggerimento.
RATIONALE_DESCRIPTOR_COUNT: Final[int] = 3

_AROMA_INDICES: Final[tuple[int, ...]] = tuple(
    FLAVOR_DESCRIPTORS.index(name) for name in AROMA_DESCRIPTORS
)


def aroma_affinity(left: FlavorProfile, right: FlavorProfile) -> float:
    """Coseno ristretto al blocco delle famiglie aromatiche.

    Si escludono gusti base e sensazioni tattili: due sciroppi sono entrambi
    dolcissimi e due distillati hanno entrambi calore alcolico, ma quelle
    coincidenze non dicono nulla sull'accostamento — sposterebbero solo
    tutti i pesi verso l'alto in modo uniforme, che equivale a non
    misurare niente.
    """
    left_aroma = [left.components[index] for index in _AROMA_INDICES]
    right_aroma = [right.components[index] for index in _AROMA_INDICES]

    left_norm = math.sqrt(sum(value * value for value in left_aroma))
    right_norm = math.sqrt(sum(value * value for value in right_aroma))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0

    dot = sum(a * b for a, b in zip(left_aroma, right_aroma, strict=True))
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def shared_aroma_descriptors(
    left: FlavorProfile, right: FlavorProfile, limit: int = RATIONALE_DESCRIPTOR_COUNT
) -> tuple[str, ...]:
    """Le famiglie aromatiche che i due condividono più intensamente.

    L'intensità condivisa è il minimo fra le due: un aroma presente al 90%
    in uno e al 10% nell'altro non è un terreno comune.
    """
    overlaps = [
        (name, min(left.components[index], right.components[index]))
        for name, index in zip(AROMA_DESCRIPTORS, _AROMA_INDICES, strict=True)
    ]
    overlaps = [(name, value) for name, value in overlaps if value > 0.0]
    overlaps.sort(key=lambda item: (-item[1], item[0]))
    return tuple(name for name, _ in overlaps[:limit])


def co_occurrence_weights(recipes: Sequence[Recipe]) -> dict[tuple[str, str], float]:
    """Quanto spesso due ingredienti compaiono nella stessa ricetta.

    Normalizzato come un coseno sull'incidenza: `n_ij / sqrt(n_i · n_j)`.
    Senza normalizzazione un ingrediente presente ovunque — lo sciroppo
    semplice — risulterebbe affine a tutto, che è vero in senso statistico
    e inutile in senso pratico.
    """
    appearances: Counter[str] = Counter()
    pairs: Counter[tuple[str, str]] = Counter()

    for recipe in recipes:
        ids = sorted({item.ingredient.id for item in recipe.ingredients})
        appearances.update(ids)
        for position, first in enumerate(ids):
            for second in ids[position + 1 :]:
                pairs[(first, second)] += 1

    return {
        pair: count / math.sqrt(appearances[pair[0]] * appearances[pair[1]])
        for pair, count in pairs.items()
    }


@dataclass(frozen=True, slots=True)
class GraphStats:
    """Forma del grafo: utile in diagnostica e in risposta all'API."""

    nodes: int
    edges: int
    density: float
    communities: int


class FlavorGraph:
    """Grafo delle affinità, con le interrogazioni che ne giustificano l'uso."""

    def __init__(self, graph: nx.Graph, ingredients: dict[str, Ingredient]) -> None:
        self._graph = graph
        self._ingredients = ingredients

    # -- Costruzione -------------------------------------------------------

    @classmethod
    def build(cls, ingredients: Iterable[Ingredient], recipes: Sequence[Recipe]) -> FlavorGraph:
        """Costruisce il grafo da dispensa e ricette.

        Solo gli ingredienti profilati entrano: senza vettore di sapore un
        nodo non avrebbe archi aromatici, comparirebbe isolato e il
        PageRank lo tratterebbe come irraggiungibile — un risultato
        corretto ma fuorviante, perché l'ingrediente non è "poco affine",
        è semplicemente non ancora descritto.
        """
        profiled = {
            ingredient.id: ingredient
            for ingredient in ingredients
            if ingredient.flavor_profile is not None
        }

        graph = nx.Graph()
        for ingredient_id, ingredient in profiled.items():
            graph.add_node(ingredient_id, name=ingredient.name)

        co_occurrence = co_occurrence_weights(recipes)
        ordered = sorted(profiled)

        for position, first_id in enumerate(ordered):
            first = profiled[first_id]
            assert first.flavor_profile is not None  # noqa: S101  (filtrato sopra)
            for second_id in ordered[position + 1 :]:
                second = profiled[second_id]
                assert second.flavor_profile is not None  # noqa: S101

                aroma = aroma_affinity(first.flavor_profile, second.flavor_profile)
                together = co_occurrence.get((first_id, second_id), 0.0)
                weight = (CO_OCCURRENCE_WEIGHT * together) + (AROMA_WEIGHT * aroma)

                if weight >= MIN_EDGE_WEIGHT:
                    graph.add_edge(
                        first_id,
                        second_id,
                        weight=weight,
                        aroma=aroma,
                        co_occurrence=together,
                    )

        return cls(graph, profiled)

    # -- Serializzazione per la cache --------------------------------------

    def to_payload(self) -> str:
        """Solo gli archi: i nodi si ricostruiscono dalla dispensa.

        Serializzare anche gli ingredienti duplicherebbe in cache dati che
        il chiamante ha già caricato, e renderebbe la cache stantia ogni
        volta che cambia un campo qualunque di un ingrediente.
        """
        return json.dumps(
            {
                "edges": [
                    [first, second, data["weight"], data["aroma"], data["co_occurrence"]]
                    for first, second, data in self._graph.edges(data=True)
                ]
            },
            separators=(",", ":"),
        )

    @classmethod
    def from_payload(cls, payload: str, ingredients: Iterable[Ingredient]) -> FlavorGraph | None:
        """Ricostruisce il grafo da una cache. `None` se il payload è illeggibile.

        Una cache corrotta non deve far fallire una richiesta: il chiamante
        ricostruisce il grafo e riscrive la voce.
        """
        try:
            data: dict[str, Any] = json.loads(payload)
            edges = data["edges"]
        except (ValueError, KeyError, TypeError):
            return None

        profiled = {
            ingredient.id: ingredient
            for ingredient in ingredients
            if ingredient.flavor_profile is not None
        }

        graph = nx.Graph()
        for ingredient_id, ingredient in profiled.items():
            graph.add_node(ingredient_id, name=ingredient.name)

        for edge in edges:
            first, second, weight, aroma, together = edge
            # Un arco verso un ingrediente nel frattempo disattivato o
            # cancellato va ignorato, non ricreato: il grafo deve riflettere
            # la dispensa di adesso.
            if first in profiled and second in profiled:
                graph.add_edge(first, second, weight=weight, aroma=aroma, co_occurrence=together)

        return cls(graph, profiled)

    # -- Interrogazioni -----------------------------------------------------

    @property
    def ingredients(self) -> tuple[Ingredient, ...]:
        """Gli ingredienti che sono davvero entrati nel grafo (quelli profilati)."""
        return tuple(self._ingredients.values())

    @property
    def stats(self) -> GraphStats:
        return GraphStats(
            nodes=self._graph.number_of_nodes(),
            edges=self._graph.number_of_edges(),
            density=nx.density(self._graph) if self._graph.number_of_nodes() > 1 else 0.0,
            communities=len(self.communities()),
        )

    def suggest(self, seed_ids: Sequence[str], limit: int = 5) -> list[PairingSuggestion]:
        """Cosa aggiungere a una ricetta in costruzione.

        PageRank personalizzato: si inietta probabilità sui nodi già in
        ricetta e si lascia diffondere sugli archi. Il risultato non è la
        somma di classifiche indipendenti — un ingrediente moderatamente
        affine a *tutti* i semi batte uno fortissimamente affine a uno solo,
        che è il comportamento giusto per un drink, dove ogni componente
        deve convivere con tutte le altre.
        """
        present = [node for node in seed_ids if node in self._graph]
        if not present or self._graph.number_of_edges() == 0:
            return []

        personalization = {node: 0.0 for node in self._graph}
        for node in present:
            personalization[node] = 1.0 / len(present)

        ranked: dict[str, float] = nx.pagerank(
            self._graph, personalization=personalization, weight="weight"
        )

        seeds = set(present)
        suggestions: list[PairingSuggestion] = []

        for node, score in sorted(ranked.items(), key=lambda item: -item[1]):
            if node in seeds or node not in self._ingredients:
                continue
            candidate = self._ingredients[node]
            if self._is_redundant(candidate, seeds):
                continue

            suggestions.append(
                PairingSuggestion(
                    ingredient=candidate,
                    affinity=score,
                    rationale=self._explain(node, seeds),
                )
            )
            if len(suggestions) >= limit:
                break

        return suggestions

    def bridge(self, source_id: str, target_id: str) -> FlavorBridge | None:
        """Il percorso di massima affinità fra due ingredienti.

        Il cammino minimo si calcola su `-log(peso)`: sommare i logaritmi
        equivale a moltiplicare le affinità, quindi il percorso "più corto"
        è quello che massimizza il prodotto delle affinità lungo la catena.
        Minimizzare la somma dei pesi grezzi darebbe invece la risposta
        opposta — preferirebbe i legami deboli.
        """
        if source_id not in self._graph or target_id not in self._graph:
            return None

        def cost(_: str, __: str, data: dict[str, Any]) -> float:
            return -math.log(max(float(data["weight"]), 1e-12))

        try:
            # Il costo è calcolato al volo invece di essere scritto sugli
            # archi: il grafo può arrivare dalla cache ed essere condiviso,
            # e un'interrogazione di lettura non deve modificarlo.
            path = nx.shortest_path(self._graph, source=source_id, target=target_id, weight=cost)
        except nx.NetworkXNoPath:
            return None

        strength = 1.0
        for first, second in zip(path[:-1], path[1:], strict=True):
            strength *= float(self._graph[first][second]["weight"])

        return FlavorBridge(
            path=tuple(self._ingredients[node] for node in path),
            strength=strength,
        )

    def communities(self) -> list[frozenset[str]]:
        """Le "famiglie" in cui la dispensa si divide da sola.

        Rilevamento per modularità: raggruppa i nodi più densamente
        connessi fra loro che con il resto. Non è una classificazione
        merceologica imposta a priori — è la struttura che emerge dagli
        aromi e dalle ricette, e può benissimo mettere un amaro insieme a
        un vermouth e lontano da un altro amaro.
        """
        if self._graph.number_of_edges() == 0:
            return []
        found = nx.community.greedy_modularity_communities(self._graph, weight="weight")
        return [frozenset(group) for group in found]

    # -- Interni -------------------------------------------------------------

    def _is_redundant(self, candidate: Ingredient, seeds: set[str]) -> bool:
        """True se il candidato è un doppione di qualcosa già in ricetta."""
        if candidate.flavor_profile is None:
            return False
        for seed_id in seeds:
            seed = self._ingredients.get(seed_id)
            if seed is None or seed.flavor_profile is None:
                continue
            if candidate.flavor_profile.cosine_similarity(seed.flavor_profile) >= (
                REDUNDANCY_THRESHOLD
            ):
                return True
        return False

    def _explain(self, node: str, seeds: set[str]) -> str:
        """Motivazione leggibile del suggerimento.

        Si cita il seme con cui il legame è più forte, perché è quello che
        ha davvero trainato il punteggio, e si dice da dove viene
        l'affinità: una ricetta esistente pesa diversamente da
        un'inferenza sugli aromi, e chi legge ha diritto di saperlo.
        """
        strongest_seed: str | None = None
        strongest_weight = 0.0
        for seed_id in seeds:
            if self._graph.has_edge(node, seed_id):
                weight = float(self._graph[node][seed_id]["weight"])
                if weight > strongest_weight:
                    strongest_weight = weight
                    strongest_seed = seed_id

        if strongest_seed is None:
            return "affine per propagazione indiretta sul grafo, senza legame diretto"

        seed = self._ingredients[strongest_seed]
        candidate = self._ingredients[node]
        edge = self._graph[node][strongest_seed]

        if edge["co_occurrence"] > 0:
            return f"compare insieme a {seed.name} in ricette esistenti" + self._aroma_clause(
                candidate, seed
            )
        return f"condivide il profilo aromatico di {seed.name}" + self._aroma_clause(
            candidate, seed
        )

    @staticmethod
    def _aroma_clause(candidate: Ingredient, seed: Ingredient) -> str:
        if candidate.flavor_profile is None or seed.flavor_profile is None:
            return ""
        shared = shared_aroma_descriptors(candidate.flavor_profile, seed.flavor_profile)
        if not shared:
            return ""
        return f" ({', '.join(shared)})"
