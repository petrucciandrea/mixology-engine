"""Traduzione fra modelli ORM ed entità di dominio.

Isolare il mapping in un modulo significa che c'è un solo posto da
guardare quando schema e dominio divergono, e che le due rappresentazioni
possono evolvere separatamente.

La direzione ORM → dominio ricostruisce entità *valide*: attraversa gli
`__post_init__`, quindi una riga corrotta nel database viene intercettata
al caricamento invece di propagarsi silenziosamente nei calcoli.
"""

from __future__ import annotations

from app.domain.entities import Ingredient, PhysicalProfile, Recipe, RecipeIngredient
from app.domain.flavor import FlavorProfile

from .models import IngredientModel, RecipeIngredientModel, RecipeModel

#: Cifre decimali conservate nel profilo organolettico.
#:
#: Il tipo `vector` di pgvector e' a **singola precisione**: 0.8 scritto in
#: colonna torna 0.800000011920929. Le intensita' dei descrittori sono
#: valori compilati a mano con due o tre decimali, quindi quelle cifre in
#: piu' non sono informazione ma rumore di rappresentazione. Arrotondare in
#: lettura rende il round-trip esatto e le entita' confrontabili con `==`,
#: cosa che senza sarebbe impossibile e costringerebbe ogni test a una
#: tolleranza.
_FLAVOR_DECIMALS = 6


def ingredient_to_domain(row: IngredientModel) -> Ingredient:
    return Ingredient(
        id=row.id,
        name=row.name,
        category=row.category,
        physical_profile=PhysicalProfile(
            density_g_ml=row.density_g_ml,
            brix=row.brix,
            acidity=row.acidity,
            abv=row.abv,
        ),
        flavor_profile=(
            FlavorProfile(
                components=tuple(
                    round(float(value), _FLAVOR_DECIMALS) for value in row.flavor_vector
                )
            )
            if row.flavor_vector is not None
            else None
        ),
        is_active=row.is_active,
    )


def ingredient_to_row(entity: Ingredient, row: IngredientModel | None = None) -> IngredientModel:
    """Crea o aggiorna la riga ORM a partire dall'entità.

    Accetta una riga esistente perché l'aggiornamento deve avvenire
    sull'istanza *tracciata dalla sessione*: sostituirla con un oggetto
    nuovo con lo stesso id farebbe perdere a SQLAlchemy la traccia delle
    modifiche.
    """
    target = row or IngredientModel(id=entity.id)
    target.name = entity.name
    target.category = entity.category
    target.density_g_ml = entity.physical_profile.density_g_ml
    target.brix = entity.physical_profile.brix
    target.acidity = entity.physical_profile.acidity
    target.abv = entity.physical_profile.abv
    target.flavor_vector = (
        list(entity.flavor_profile.components) if entity.flavor_profile is not None else None
    )
    target.is_active = entity.is_active
    return target


def recipe_to_domain(row: RecipeModel) -> Recipe:
    return Recipe(
        id=row.id,
        name=row.name,
        dilution_method=row.dilution_method,
        serving_ice=row.serving_ice,
        glass=row.glass,
        instructions=row.instructions,
        ingredients=tuple(
            RecipeIngredient(
                ingredient=ingredient_to_domain(item.ingredient),
                volume_ml=item.volume_ml,
            )
            # L'ordinamento è già imposto dalla relationship, ma ripeterlo
            # qui rende il mapper indipendente da come la riga è stata
            # caricata (query diretta, lazy load, refresh).
            for item in sorted(row.ingredients, key=lambda item: item.position)
        ),
    )


def recipe_to_row(entity: Recipe, row: RecipeModel | None = None) -> RecipeModel:
    target = row or RecipeModel(id=entity.id)
    target.name = entity.name
    target.dilution_method = entity.dilution_method
    target.serving_ice = entity.serving_ice
    target.glass = entity.glass
    target.instructions = entity.instructions

    # Il dosaggio viene sostituito per intero: `Recipe` è un aggregate, e
    # la sua lista di ingredienti non ha identità propria da preservare.
    # `delete-orphan` sulla relationship si occupa di rimuovere le righe
    # che non compaiono più.
    target.ingredients = [
        RecipeIngredientModel(
            recipe_id=entity.id,
            ingredient_id=item.ingredient.id,
            volume_ml=item.volume_ml,
            position=position,
        )
        for position, item in enumerate(entity.ingredients)
    ]
    return target
