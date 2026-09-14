"""Popola il database con una dispensa e alcune ricette di riferimento.

    make seed

I valori fisici sono dati reali di prodotto, non numeri di comodo: sono le
grandezze con cui il solver lavora, e un seed approssimativo produrrebbe
bilanciamenti approssimativi. Dove un prodotto commerciale varia (gli
zuccheri residui di un rum invecchiato, il Brix di uno sciroppo d'agave)
si è scelto un valore centrale e rappresentativo.

Riferimenti per le grandezze meno ovvie:
  * succo di lime ~6% di acido citrico, 7.5 °Bx; limone ~5.5% e 2.5 °Bx;
  * sciroppo semplice 1:1 in peso = 50 °Bx, densità 1.23 g/ml;
  * sciroppo ricco 2:1 = 65 °Bx, densità 1.31 g/ml;
  * i liquori portano zucchero: il triple sec sta intorno ai 25 °Bx, e
    ignorarlo sposta il Brix di un Margarita di diversi punti.

Lo script è idempotente: un ingrediente o una ricetta già presenti vengono
saltati, quindi si può rilanciare senza duplicare nulla.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Ingredient, PhysicalProfile, Recipe, RecipeIngredient
from app.domain.enums import DilutionMethod, IngredientCategory
from app.domain.flavor import FlavorProfile
from app.infrastructure.db.repositories import (
    SqlAlchemyIngredientRepository,
    SqlAlchemyRecipeRepository,
)
from app.infrastructure.db.session import dispose_engine, get_session_factory


@dataclass(frozen=True)
class Spec:
    """Riga della dispensa: profilo fisico più profilo organolettico."""

    name: str
    category: IngredientCategory
    abv: float
    brix: float
    acidity: float
    density: float
    flavor: dict[str, float]


BAR: tuple[Spec, ...] = (
    # --- Distillati ---------------------------------------------------
    Spec(
        "London Dry Gin",
        IngredientCategory.SPIRIT,
        0.43,
        0.0,
        0.0,
        0.94,
        {"alcohol_heat": 0.65, "resinous": 0.8, "citrus": 0.4, "pepper": 0.3, "herbaceous": 0.35},
    ),
    Spec(
        "Rum Bianco",
        IngredientCategory.SPIRIT,
        0.40,
        0.0,
        0.0,
        0.95,
        {"alcohol_heat": 0.6, "tropical_fruit": 0.35, "funky": 0.25, "vanilla": 0.15},
    ),
    Spec(
        "Rum Invecchiato",
        IngredientCategory.SPIRIT,
        0.40,
        1.0,
        0.0,
        0.95,
        {
            "alcohol_heat": 0.55,
            "sweet": 0.2,
            "vanilla": 0.6,
            "caramel": 0.55,
            "dried_fruit": 0.4,
            "woody": 0.45,
        },
    ),
    Spec(
        "Bourbon",
        IngredientCategory.SPIRIT,
        0.45,
        0.0,
        0.0,
        0.94,
        {"alcohol_heat": 0.7, "vanilla": 0.7, "caramel": 0.6, "woody": 0.5, "warm_spice": 0.3},
    ),
    Spec(
        "Rye Whiskey",
        IngredientCategory.SPIRIT,
        0.45,
        0.0,
        0.0,
        0.94,
        {"alcohol_heat": 0.7, "pepper": 0.6, "warm_spice": 0.5, "woody": 0.45, "vanilla": 0.35},
    ),
    Spec(
        "Tequila Blanco",
        IngredientCategory.SPIRIT,
        0.40,
        0.0,
        0.0,
        0.95,
        {"alcohol_heat": 0.6, "herbaceous": 0.5, "earthy": 0.4, "pepper": 0.35},
    ),
    Spec(
        "Mezcal",
        IngredientCategory.SPIRIT,
        0.45,
        0.0,
        0.0,
        0.94,
        {"alcohol_heat": 0.7, "smoke": 0.9, "earthy": 0.6, "herbaceous": 0.35},
    ),
    Spec(
        "Cognac VSOP",
        IngredientCategory.SPIRIT,
        0.40,
        1.0,
        0.0,
        0.95,
        {
            "alcohol_heat": 0.6,
            "stone_fruit": 0.45,
            "dried_fruit": 0.5,
            "woody": 0.5,
            "vanilla": 0.4,
        },
    ),
    # --- Liquori ------------------------------------------------------
    Spec(
        "Triple Sec",
        IngredientCategory.LIQUEUR,
        0.40,
        25.0,
        0.0,
        1.04,
        {"sweet": 0.7, "citrus": 0.9, "alcohol_heat": 0.4, "floral": 0.2},
    ),
    Spec(
        "Maraschino",
        IngredientCategory.LIQUEUR,
        0.32,
        30.0,
        0.0,
        1.08,
        {"sweet": 0.75, "stone_fruit": 0.7, "nutty": 0.5, "floral": 0.3},
    ),
    Spec(
        "Chartreuse Verde",
        IngredientCategory.LIQUEUR,
        0.55,
        25.0,
        0.0,
        1.03,
        {
            "sweet": 0.6,
            "alcohol_heat": 0.8,
            "herbaceous": 0.95,
            "mint": 0.5,
            "anise": 0.4,
            "medicinal": 0.3,
        },
    ),
    Spec(
        "Falernum",
        IngredientCategory.LIQUEUR,
        0.11,
        35.0,
        0.3,
        1.13,
        {"sweet": 0.85, "warm_spice": 0.6, "nutty": 0.5, "citrus": 0.4},
    ),
    Spec(
        "Orgeat",
        IngredientCategory.SYRUP,
        0.0,
        55.0,
        0.0,
        1.26,
        {"sweet": 0.95, "nutty": 0.9, "floral": 0.4},
    ),
    # --- Vini fortificati ----------------------------------------------
    Spec(
        "Vermouth Rosso",
        IngredientCategory.FORTIFIED_WINE,
        0.16,
        16.0,
        0.5,
        1.05,
        {
            "sweet": 0.6,
            "bitter": 0.3,
            "dried_fruit": 0.5,
            "warm_spice": 0.4,
            "herbaceous": 0.3,
            "woody": 0.2,
        },
    ),
    Spec(
        "Vermouth Dry",
        IngredientCategory.FORTIFIED_WINE,
        0.18,
        4.0,
        0.6,
        1.00,
        {"sour": 0.3, "bitter": 0.25, "herbaceous": 0.6, "floral": 0.35, "orchard_fruit": 0.3},
    ),
    Spec(
        "Sherry Fino",
        IngredientCategory.FORTIFIED_WINE,
        0.15,
        1.0,
        0.4,
        0.99,
        {"salty": 0.4, "sour": 0.25, "nutty": 0.6, "funky": 0.4, "orchard_fruit": 0.3},
    ),
    # --- Bitter e amari -------------------------------------------------
    Spec(
        "Bitter Rosso",
        IngredientCategory.BITTER,
        0.25,
        24.0,
        0.4,
        1.06,
        {"bitter": 0.95, "sweet": 0.5, "citrus": 0.5, "medicinal": 0.4, "floral": 0.2},
    ),
    Spec(
        "Aperitivo Arancione",
        IngredientCategory.BITTER,
        0.11,
        28.0,
        0.4,
        1.09,
        {"bitter": 0.6, "sweet": 0.7, "citrus": 0.7, "medicinal": 0.2},
    ),
    Spec(
        "Amaro d'Erbe",
        IngredientCategory.AMARO,
        0.23,
        30.0,
        0.3,
        1.09,
        {"bitter": 0.7, "sweet": 0.7, "herbaceous": 0.6, "warm_spice": 0.5, "dried_fruit": 0.35},
    ),
    Spec(
        "Angostura Bitters",
        IngredientCategory.BITTER,
        0.44,
        5.0,
        0.0,
        0.98,
        {"bitter": 0.9, "warm_spice": 0.9, "alcohol_heat": 0.7, "woody": 0.4},
    ),
    # --- Succhi ----------------------------------------------------------
    Spec(
        "Succo di Lime",
        IngredientCategory.JUICE,
        0.0,
        7.5,
        6.0,
        1.03,
        {"sour": 0.95, "citrus": 0.9, "herbaceous": 0.2},
    ),
    Spec(
        "Succo di Limone",
        IngredientCategory.JUICE,
        0.0,
        2.5,
        5.5,
        1.02,
        {"sour": 0.95, "citrus": 0.95, "floral": 0.15},
    ),
    Spec(
        "Succo di Pompelmo",
        IngredientCategory.JUICE,
        0.0,
        9.0,
        2.0,
        1.04,
        {"sour": 0.6, "bitter": 0.4, "citrus": 0.85, "floral": 0.2},
    ),
    Spec(
        "Succo d'Ananas",
        IngredientCategory.JUICE,
        0.0,
        12.0,
        0.8,
        1.05,
        {"sweet": 0.65, "sour": 0.4, "tropical_fruit": 0.95, "funky": 0.2},
    ),
    # --- Sciroppi e soluzioni --------------------------------------------
    Spec("Sciroppo Semplice 1:1", IngredientCategory.SYRUP, 0.0, 50.0, 0.0, 1.23, {"sweet": 1.0}),
    Spec(
        "Sciroppo Ricco 2:1",
        IngredientCategory.SYRUP,
        0.0,
        65.0,
        0.0,
        1.31,
        {"sweet": 1.0, "caramel": 0.15},
    ),
    Spec(
        "Sciroppo d'Agave",
        IngredientCategory.SYRUP,
        0.0,
        76.0,
        0.0,
        1.38,
        {"sweet": 1.0, "earthy": 0.25, "honey": 0.4},
    ),
    Spec(
        "Soluzione Citrica 6%",
        IngredientCategory.ACID_SOLUTION,
        0.0,
        0.0,
        6.0,
        1.02,
        {"sour": 1.0},
    ),
    Spec("Soda", IngredientCategory.MIXER, 0.0, 0.0, 0.0, 1.00, {"pungency": 0.3}),
)


#: Ricette classiche, con il dosaggio canonico. Sono il banco di prova del
#: solver: si parte da qui, si chiede un target e si guarda di quanto si
#: sposta rispetto alla tradizione.
CLASSICS: tuple[tuple[str, DilutionMethod, str, tuple[tuple[str, float], ...]], ...] = (
    (
        "Daiquiri",
        DilutionMethod.SHAKEN,
        "Shake energico con ghiaccio, doppio filtro, coppetta ghiacciata.",
        (("Rum Bianco", 60.0), ("Succo di Lime", 30.0), ("Sciroppo Semplice 1:1", 20.0)),
    ),
    (
        "Negroni",
        DilutionMethod.STIRRED,
        "Mescolare nel mixing glass con ghiaccio, servire su ghiaccio, scorza d'arancia.",
        (("London Dry Gin", 30.0), ("Vermouth Rosso", 30.0), ("Bitter Rosso", 30.0)),
    ),
    (
        "Margarita",
        DilutionMethod.SHAKEN,
        "Shake con ghiaccio, coppetta con bordo di sale a metà.",
        (("Tequila Blanco", 50.0), ("Triple Sec", 20.0), ("Succo di Lime", 25.0)),
    ),
    (
        "Last Word",
        DilutionMethod.SHAKEN,
        "Quattro parti uguali. Shake, doppio filtro, coppetta.",
        (
            ("London Dry Gin", 22.5),
            ("Chartreuse Verde", 22.5),
            ("Maraschino", 22.5),
            ("Succo di Lime", 22.5),
        ),
    ),
    (
        "Whiskey Sour",
        DilutionMethod.SHAKEN,
        "Shake con ghiaccio, servire su ghiaccio, angostura in superficie.",
        (("Bourbon", 60.0), ("Succo di Limone", 25.0), ("Sciroppo Semplice 1:1", 20.0)),
    ),
    (
        "Mai Tai",
        DilutionMethod.SHAKEN,
        "Shake, servire su ghiaccio tritato, menta e mezza lime.",
        (
            ("Rum Invecchiato", 45.0),
            ("Triple Sec", 15.0),
            ("Orgeat", 15.0),
            ("Succo di Lime", 22.5),
        ),
    ),
)


async def seed_ingredients(session: AsyncSession) -> dict[str, Ingredient]:
    repository = SqlAlchemyIngredientRepository(session)
    catalogue: dict[str, Ingredient] = {}
    created = 0

    for spec in BAR:
        existing = await repository.get_by_name(spec.name)
        if existing is not None:
            catalogue[spec.name] = existing
            continue

        ingredient = Ingredient(
            id=str(uuid.uuid4()),
            name=spec.name,
            category=spec.category,
            physical_profile=PhysicalProfile(
                density_g_ml=spec.density,
                brix=spec.brix,
                acidity=spec.acidity,
                abv=spec.abv,
            ),
            flavor_profile=FlavorProfile.from_descriptors(**spec.flavor),
        )
        catalogue[spec.name] = await repository.add(ingredient)
        created += 1

    print(f"Ingredienti: {created} creati, {len(BAR) - created} già presenti.")
    return catalogue


async def seed_recipes(session: AsyncSession, catalogue: dict[str, Ingredient]) -> None:
    repository = SqlAlchemyRecipeRepository(session)
    existing_names = {recipe.name for recipe in await repository.list(limit=500)}
    created = 0

    for name, method, instructions, doses in CLASSICS:
        if name in existing_names:
            continue
        await repository.add(
            Recipe(
                id=str(uuid.uuid4()),
                name=name,
                dilution_method=method,
                instructions=instructions,
                ingredients=tuple(
                    RecipeIngredient(ingredient=catalogue[ingredient_name], volume_ml=volume)
                    for ingredient_name, volume in doses
                ),
            )
        )
        created += 1

    print(f"Ricette: {created} create, {len(CLASSICS) - created} già presenti.")


async def main() -> None:
    factory = get_session_factory()
    async with factory() as session:
        catalogue = await seed_ingredients(session)
        await seed_recipes(session, catalogue)
        # Un solo commit: o la dispensa entra intera, o non entra affatto.
        # Una dispensa a metà produrrebbe ricette con riferimenti mancanti.
        await session.commit()
    await dispose_engine()
    print("Seed completato.")


if __name__ == "__main__":
    asyncio.run(main())
