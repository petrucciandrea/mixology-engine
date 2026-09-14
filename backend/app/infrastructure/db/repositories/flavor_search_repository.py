"""Ricerca vettoriale su pgvector."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Ingredient
from app.domain.enums import IngredientCategory
from app.domain.flavor import FlavorProfile
from app.domain.matching import SimilarityHit

from ..mappers import ingredient_to_domain
from ..models import IngredientModel, RecipeIngredientModel, RecipeModel


class SqlAlchemyFlavorSearchRepository:
    """Implementazione della porta `FlavorSearchRepository`.

    L'ordinamento per distanza avviene **nel database**, sull'indice HNSW
    creato dalla migrazione iniziale. È l'unico modo di sfruttarlo:
    caricare la dispensa e ordinarla in Python funzionerebbe su trenta
    ingredienti e crollerebbe su trentamila, vanificando la ragione stessa
    per cui si è scelto pgvector.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_similar(
        self,
        profile: FlavorProfile,
        *,
        limit: int = 10,
        exclude_ids: Sequence[str] = (),
        category: IngredientCategory | None = None,
        active_only: bool = True,
    ) -> list[SimilarityHit]:
        # `cosine_distance` è l'operatore `<=>` di pgvector: 0 = stessa
        # direzione, 1 = ortogonali. La similarità è il suo complemento, ed è
        # la stessa grandezza calcolata da `FlavorProfile.cosine_similarity`
        # nel dominio — che resta l'implementazione di riferimento contro cui
        # i test verificano questa.
        distance = IngredientModel.flavor_vector.cosine_distance(list(profile.components))

        statement = (
            select(IngredientModel, distance.label("distance"))
            # Un ingrediente senza profilo non è "lontano": è non confrontabile,
            # e includerlo lo farebbe comparire in fondo alla classifica come
            # se fosse stato valutato.
            .where(IngredientModel.flavor_vector.is_not(None))
            .order_by(distance)
            .limit(limit)
        )

        if exclude_ids:
            statement = statement.where(IngredientModel.id.notin_(list(exclude_ids)))
        if category is not None:
            statement = statement.where(IngredientModel.category == category)
        if active_only:
            statement = statement.where(IngredientModel.is_active.is_(True))

        rows = (await self._session.execute(statement)).all()

        return [
            SimilarityHit(
                ingredient=ingredient_to_domain(row[0]),
                # Il clamp assorbe l'errore in virgola mobile della distanza
                # calcolata in singola precisione, che su vettori identici può
                # restituire un epsilon negativo.
                similarity=max(0.0, min(1.0, 1.0 - float(row[1]))),
            )
            for row in rows
        ]

    async def list_profiled(self, *, active_only: bool = True) -> list[Ingredient]:
        statement = (
            select(IngredientModel)
            .where(IngredientModel.flavor_vector.is_not(None))
            .order_by(IngredientModel.name)
        )
        if active_only:
            statement = statement.where(IngredientModel.is_active.is_(True))

        rows = (await self._session.execute(statement)).scalars().all()
        return [ingredient_to_domain(row) for row in rows]

    async def graph_fingerprint(self) -> str:
        """Impronta compatta degli ingressi del grafo.

        Due sole query di aggregazione, entrambe servite dagli indici. Si
        usano conteggio e data di ultima modifica per ciascuna delle tre
        tabelle che il grafo legge: cambia un ingrediente profilato, una
        ricetta o un dosaggio, e l'impronta cambia con esso.

        `recipe_ingredients` non ha un proprio `updated_at`, quindi entra
        con il solo conteggio: un dosaggio modificato senza aggiungere o
        togliere righe muove comunque `recipes.updated_at`, perché passa
        dallo stesso aggregate.
        """
        ingredients = (
            await self._session.execute(
                select(
                    func.count(IngredientModel.id),
                    func.max(IngredientModel.updated_at),
                ).where(IngredientModel.flavor_vector.is_not(None))
            )
        ).one()

        recipes = (
            await self._session.execute(
                select(
                    func.count(RecipeModel.id),
                    func.max(RecipeModel.updated_at),
                    select(func.count(RecipeIngredientModel.id)).scalar_subquery(),
                )
            )
        ).one()

        return "|".join(str(part) for part in (*ingredients, *recipes))
