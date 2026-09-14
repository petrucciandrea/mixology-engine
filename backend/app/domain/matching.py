"""Tipi e porte del matcher organolettico.

Il matcher risponde a due domande diverse, che questo modulo tiene
distinte perché richiedono relazioni opposte fra gli ingredienti:

* **"con cosa posso sostituirlo?"** → *similarità*. Il candidato deve
  somigliare all'originale.
* **"cosa ci sta bene insieme?"** → *affinità*. Il candidato non deve
  somigliare a ciò che c'è già: due succhi di agrume simili sono
  ridondanti, non complementari.

Confonderle in un solo punteggio produce il difetto classico dei
sistemi di raccomandazione applicati al cibo — suggerire il limone a chi
ha già il lime.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .entities import Ingredient
from .enums import IngredientCategory
from .flavor import FlavorProfile
from .services.substitution import SubstitutionScore


@dataclass(frozen=True, slots=True)
class SimilarityHit:
    """Un ingrediente restituito da una ricerca vettoriale, con il suo punteggio.

    La similarità arriva dal database (pgvector la calcola sull'indice);
    l'entità è già mappata a dominio, così il layer applicativo non vede
    mai una riga ORM.
    """

    ingredient: Ingredient
    similarity: float


@dataclass(frozen=True, slots=True)
class SubstitutionCandidate:
    """Un sostituto proposto, con la motivazione del punteggio."""

    ingredient: Ingredient
    score: SubstitutionScore

    @property
    def overall(self) -> float:
        return self.score.overall


@dataclass(frozen=True, slots=True)
class PairingSuggestion:
    """Un ingrediente suggerito per completare una ricetta.

    `rationale` non è decorazione: senza, un suggerimento è un nome estratto
    da una scatola nera, e chi compone la ricetta non ha modo di valutarlo
    se non provandolo.
    """

    ingredient: Ingredient
    affinity: float
    rationale: str


@dataclass(frozen=True, slots=True)
class FlavorBridge:
    """Il percorso più affine fra due ingredienti lontani.

    Risponde a "come arrivo dal mezcal alla fragola?": gli ingredienti
    intermedi sono quelli che rendono plausibile l'accostamento, ed è il
    modo in cui si costruisce un drink d'autore attorno a un'idea, invece
    di accostare due elementi che non si parlano.
    """

    path: tuple[Ingredient, ...]
    #: Prodotto delle affinità lungo il percorso, in [0, 1].
    strength: float


class FlavorSearchRepository(Protocol):
    """Porta per la ricerca vettoriale.

    Esiste separata da `IngredientRepository` perché è un'operazione di
    natura diversa — una ricerca per prossimità su un indice, non un
    accesso per chiave — e perché un domani potrebbe essere servita da un
    motore dedicato senza toccare la persistenza ordinaria.
    """

    async def find_similar(
        self,
        profile: FlavorProfile,
        *,
        limit: int = 10,
        exclude_ids: Sequence[str] = (),
        category: IngredientCategory | None = None,
        active_only: bool = True,
    ) -> list[SimilarityHit]:
        """Ingredienti più vicini al profilo, dal più simile.

        L'ordinamento e il taglio avvengono nel database: è l'unico modo di
        sfruttare l'indice HNSW, e caricare l'intera dispensa per ordinarla
        in memoria vanificherebbe la ragione stessa di usare pgvector.
        """
        ...

    async def list_profiled(self, *, active_only: bool = True) -> list[Ingredient]:
        """Tutti gli ingredienti che hanno un profilo organolettico.

        Serve a costruire il grafo delle affinità, che ragiona sull'intera
        dispensa e non su una vicinanza locale.
        """
        ...

    async def graph_fingerprint(self) -> str:
        """Impronta degli ingressi del grafo: dispensa profilata e ricette.

        Cambia quando cambia qualcosa che il grafo usa, e serve come chiave
        di cache: una voce con impronta diversa non viene nemmeno letta,
        quindi l'invalidazione è automatica e non c'è modo di dimenticarsi
        di svuotare la cache dopo una modifica.
        """
        ...


class GraphSnapshotCache(Protocol):
    """Porta per la cache del grafo delle affinità.

    Il grafo si costruisce in O(n²) sulle coppie di ingredienti: con una
    dispensa da bar è istantaneo, con un catalogo da distributore no. La
    cache lo rende un costo pagato una volta per stato della dispensa.
    """

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, payload: str, ttl_seconds: int) -> None: ...
