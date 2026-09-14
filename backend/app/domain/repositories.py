"""Porte di persistenza (dependency inversion).

Qui il dominio dichiara *di cosa ha bisogno*, non *come viene fatto*.
Sono `Protocol` e non classi base astratte di proposito: i repository
concreti in `infrastructure/` non ereditano da nulla e non importano
questo modulo: la freccia della dipendenza va dall'esterno verso
l'interno, che è la definizione stessa di dependency inversion. La
conformità è verificata staticamente da MyPy nel punto di composizione
(`app/api/deps.py`), non a runtime.

Le firme sono `async` perché lo stack è interamente asincrono; questo è
l'unico punto in cui una scelta tecnologica traspare nel dominio, ed è
un compromesso consapevole: l'alternativa (porte sincrone con adapter)
aggiungerebbe un layer di traduzione senza valore reale.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .entities import Ingredient, Recipe
from .enums import IngredientCategory


class IngredientRepository(Protocol):
    """Accesso alla dispensa degli ingredienti."""

    async def get(self, ingredient_id: str) -> Ingredient | None: ...

    async def get_by_name(self, name: str) -> Ingredient | None: ...

    async def get_many(self, ingredient_ids: Sequence[str]) -> list[Ingredient]:
        """Carica più ingredienti in una sola query.

        Esiste per evitare il problema N+1 quando si compone una ricetta:
        il caso d'uso conosce tutti gli id in anticipo, e non c'è ragione
        di pagare un round-trip per ciascuno.
        """
        ...

    async def list(
        self,
        *,
        category: IngredientCategory | None = None,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Ingredient]: ...

    async def count(
        self,
        *,
        category: IngredientCategory | None = None,
        active_only: bool = True,
    ) -> int: ...

    async def add(self, ingredient: Ingredient) -> Ingredient: ...

    async def save(self, ingredient: Ingredient) -> Ingredient:
        """Inserisce o aggiorna (upsert sull'identità dell'aggregate)."""
        ...

    async def delete(self, ingredient_id: str) -> bool: ...


class RecipeRepository(Protocol):
    """Accesso alle ricette, caricate sempre con i loro ingredienti.

    `Recipe` è un aggregate root: non esiste un modo di ottenere un
    `RecipeIngredient` fuori dalla sua ricetta, perché la sua invariante
    (volumi coerenti, nessun duplicato) ha senso solo nell'insieme.
    """

    async def get(self, recipe_id: str) -> Recipe | None: ...

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[Recipe]: ...

    async def count(self) -> int: ...

    async def add(self, recipe: Recipe) -> Recipe: ...

    async def save(self, recipe: Recipe) -> Recipe: ...

    async def delete(self, recipe_id: str) -> bool: ...


class UnitOfWork(Protocol):
    """Confine transazionale.

    Senza di esso il caso d'uso non ha modo di dire "questi due scritture
    valgono insieme o non valgono", e la decisione di quando committare
    finirebbe per default nel layer HTTP — dove nessuno sa se
    l'operazione di business è conclusa.
    """

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
