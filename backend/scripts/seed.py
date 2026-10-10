"""Popola il database con una dispensa e alcune ricette di riferimento.

    make seed

I valori fisici sono dati reali di prodotto, non numeri di comodo: sono le
grandezze con cui il solver lavora, e un seed approssimativo produrrebbe
bilanciamenti approssimativi. Dove un prodotto commerciale varia (gli
zuccheri residui di un rum invecchiato, il Brix di uno sciroppo d'agave)
si è scelto un valore centrale e rappresentativo.

Riferimenti per le grandezze meno ovvie:
  * il Brix è la massa di **zucchero** ogni 100 g, non la lettura del
    rifrattometro, che conta anche gli acidi (~0.9 °Bx per punto di acidità):
    un lime letto a 7.5 °Bx ha 1.7 g di zucchero ogni 100 g. Usare la lettura
    gonfia di ~5 °Bx i succhi molto acidi e fa sembrare dolci i sour;
  * succo di lime ~6% di acido citrico, 1.7 °Bx; limone ~5.5% e 2.5 °Bx;
    pompelmo ~2% e 8 °Bx; frutto della passione ~3% e 11 °Bx;
  * sciroppo semplice 1:1 in peso = 50 °Bx, densità 1.23 g/ml;
  * sciroppo ricco 2:1 = 65 °Bx, densità 1.31 g/ml;
  * i liquori portano zucchero: il triple sec sta intorno ai 25 °Bx, e
    ignorarlo sposta il Brix di un Margarita di diversi punti.

Nomenclatura: marchio solo dove il prodotto è insostituibile (Campari,
Aperol, Angostura...), nome generico altrove; vedi il commento su `BAR`.

Lo script è idempotente: un ingrediente o una ricetta già presenti vengono
saltati, quindi si può rilanciare senza duplicare nulla. Fanno eccezione le
revisioni dichiarate: `SUPERSEDED_PROFILES` per i dati fisici degli
ingredienti, `REVISED` per le dosi delle ricette.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, replace

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Ingredient, PhysicalProfile, Recipe, RecipeIngredient
from app.domain.enums import (
    DilutionMethod,
    GlassType,
    IngredientCategory,
    RecipeFamily,
    ServingIce,
)
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


#: Vecchi nomi generici di ingredienti che il seed ora identifica per marchio.
#: Il vincolo di unicità è sul nome: senza questa mappa, un database già
#: popolato otterrebbe "Campari" accanto a "Bitter Rosso" e il Negroni
#: continuerebbe a puntare al secondo. Il seed rinomina la riga esistente,
#: così id e riferimenti nelle ricette restano intatti.
RENAMED: dict[str, str] = {
    "Bitter Rosso": "Campari",
    "Aperitivo Arancione": "Aperol",
}

# Criterio di nomenclatura. Un ingrediente porta il **marchio** solo se il
# prodotto *è* la ricetta: non esiste un equivalente generico che dia lo
# stesso risultato (Campari, Aperol, Angostura, Chartreuse, Fernet-Branca...).
# In tutti gli altri casi il nome è **generico** ("Gin", "Bourbon", "Triple
# Sec"), perché il profilo è una media rappresentativa della categoria e un
# marchio promettrebbe una precisione che il dato non ha. I valori sono
# quelli tipici di prodotto: Brix dei liquori da residuo zuccherino
# dichiarato, acidità in % p/v di acido equivalente (citrico per gli
# agrumi, tartarico per il vino).
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
        "Old Tom Gin",
        IngredientCategory.SPIRIT,
        0.43,
        6.0,
        0.0,
        0.95,
        {"alcohol_heat": 0.55, "sweet": 0.3, "resinous": 0.6, "citrus": 0.4, "herbaceous": 0.3},
    ),
    Spec(
        "Vodka",
        IngredientCategory.SPIRIT,
        0.40,
        0.0,
        0.0,
        0.95,
        {"alcohol_heat": 0.65, "pungency": 0.1},
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
        "Rhum Agricole Blanc",
        IngredientCategory.SPIRIT,
        0.50,
        0.0,
        0.0,
        0.93,
        {
            "alcohol_heat": 0.75,
            "herbaceous": 0.6,
            "earthy": 0.5,
            "funky": 0.45,
            "tropical_fruit": 0.2,
        },
    ),
    Spec(
        "Cachaça",
        IngredientCategory.SPIRIT,
        0.40,
        0.0,
        0.0,
        0.95,
        {
            "alcohol_heat": 0.6,
            "herbaceous": 0.5,
            "earthy": 0.4,
            "funky": 0.3,
            "tropical_fruit": 0.2,
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
        "Scotch Blended",
        IngredientCategory.SPIRIT,
        0.40,
        0.0,
        0.0,
        0.95,
        {
            "alcohol_heat": 0.6,
            "woody": 0.4,
            "caramel": 0.35,
            "vanilla": 0.3,
            "dried_fruit": 0.2,
            "smoke": 0.15,
        },
    ),
    Spec(
        "Scotch Islay",
        IngredientCategory.SPIRIT,
        0.46,
        0.0,
        0.0,
        0.94,
        {
            "alcohol_heat": 0.7,
            "smoke": 0.95,
            "medicinal": 0.6,
            "earthy": 0.4,
            "woody": 0.35,
            "salty": 0.2,
        },
    ),
    Spec(
        "Irish Whiskey",
        IngredientCategory.SPIRIT,
        0.40,
        0.0,
        0.0,
        0.95,
        {"alcohol_heat": 0.5, "vanilla": 0.45, "orchard_fruit": 0.4, "honey": 0.3, "woody": 0.25},
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
        "Tequila Reposado",
        IngredientCategory.SPIRIT,
        0.40,
        0.5,
        0.0,
        0.95,
        {
            "alcohol_heat": 0.55,
            "herbaceous": 0.35,
            "earthy": 0.35,
            "vanilla": 0.35,
            "woody": 0.3,
            "caramel": 0.2,
        },
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
    Spec(
        "Brandy",
        IngredientCategory.SPIRIT,
        0.40,
        1.5,
        0.0,
        0.95,
        {"alcohol_heat": 0.6, "dried_fruit": 0.4, "caramel": 0.3, "woody": 0.35, "vanilla": 0.3},
    ),
    Spec(
        "Pisco",
        IngredientCategory.SPIRIT,
        0.42,
        0.0,
        0.0,
        0.94,
        {"alcohol_heat": 0.65, "floral": 0.5, "orchard_fruit": 0.4, "herbaceous": 0.25},
    ),
    Spec(
        "Calvados",
        IngredientCategory.SPIRIT,
        0.40,
        1.0,
        0.0,
        0.95,
        {
            "alcohol_heat": 0.6,
            "orchard_fruit": 0.8,
            "woody": 0.35,
            "vanilla": 0.25,
            "warm_spice": 0.15,
        },
    ),
    Spec(
        "Grappa",
        IngredientCategory.SPIRIT,
        0.40,
        0.0,
        0.0,
        0.95,
        {
            "alcohol_heat": 0.8,
            "pungency": 0.2,
            "floral": 0.3,
            "earthy": 0.3,
            "funky": 0.25,
            "stone_fruit": 0.2,
        },
    ),
    Spec(
        "Absinthe",
        IngredientCategory.SPIRIT,
        0.65,
        0.0,
        0.0,
        0.93,
        {"alcohol_heat": 0.85, "anise": 0.95, "herbaceous": 0.7, "mint": 0.3, "cooling": 0.3},
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
        "Blue Curaçao",
        IngredientCategory.LIQUEUR,
        0.21,
        35.0,
        0.0,
        1.10,
        {"sweet": 0.85, "citrus": 0.8, "alcohol_heat": 0.2, "floral": 0.1},
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
        "Amaretto",
        IngredientCategory.LIQUEUR,
        0.28,
        40.0,
        0.0,
        1.10,
        {"sweet": 0.9, "nutty": 0.85, "stone_fruit": 0.4, "caramel": 0.2, "alcohol_heat": 0.25},
    ),
    Spec(
        "Crème de Cassis",
        IngredientCategory.LIQUEUR,
        0.15,
        40.0,
        0.5,
        1.16,
        {"sweet": 0.85, "berry": 0.95, "sour": 0.15, "astringency": 0.1},
    ),
    Spec(
        "Crème de Violette",
        IngredientCategory.LIQUEUR,
        0.20,
        30.0,
        0.0,
        1.08,
        {"sweet": 0.75, "floral": 0.95, "berry": 0.1},
    ),
    Spec(
        "Crème de Cacao Bianca",
        IngredientCategory.LIQUEUR,
        0.24,
        35.0,
        0.0,
        1.10,
        {"sweet": 0.85, "roasted": 0.6, "vanilla": 0.5, "alcohol_heat": 0.3},
    ),
    Spec(
        "Liquore di Sambuco",
        IngredientCategory.LIQUEUR,
        0.20,
        25.0,
        0.0,
        1.08,
        {"sweet": 0.8, "floral": 0.9, "stone_fruit": 0.3, "tropical_fruit": 0.2, "citrus": 0.2},
    ),
    Spec(
        "Liquore al Caffè",
        IngredientCategory.LIQUEUR,
        0.20,
        45.0,
        0.0,
        1.13,
        {"sweet": 0.85, "roasted": 0.9, "bitter": 0.25, "vanilla": 0.3, "caramel": 0.35},
    ),
    Spec(
        "Limoncello",
        IngredientCategory.LIQUEUR,
        0.28,
        30.0,
        0.0,
        1.06,
        {"sweet": 0.8, "citrus": 0.95, "alcohol_heat": 0.3},
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
        "Chartreuse Gialla",
        IngredientCategory.LIQUEUR,
        0.40,
        30.0,
        0.0,
        1.05,
        {
            "sweet": 0.75,
            "herbaceous": 0.7,
            "honey": 0.5,
            "anise": 0.35,
            "floral": 0.35,
            "alcohol_heat": 0.5,
        },
    ),
    Spec(
        "Drambuie",
        IngredientCategory.LIQUEUR,
        0.4,
        35.0,
        0.0,
        1.1,
        {
            "sweet": 0.8,
            "honey": 0.6,
            "herbaceous": 0.4,
            "warm_spice": 0.3,
            "woody": 0.25,
            "alcohol_heat": 0.45,
        },
    ),
    Spec(
        "Bénédictine",
        IngredientCategory.LIQUEUR,
        0.40,
        30.0,
        0.0,
        1.07,
        {
            "sweet": 0.75,
            "herbaceous": 0.7,
            "honey": 0.55,
            "warm_spice": 0.55,
            "woody": 0.3,
            "alcohol_heat": 0.45,
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
    # --- Vini fortificati e aromatizzati --------------------------------
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
        "Vermouth Bianco",
        IngredientCategory.FORTIFIED_WINE,
        0.15,
        13.0,
        0.5,
        1.04,
        {
            "sweet": 0.6,
            "floral": 0.5,
            "herbaceous": 0.45,
            "orchard_fruit": 0.3,
            "vanilla": 0.2,
            "bitter": 0.15,
        },
    ),
    Spec(
        "Lillet Blanc",
        IngredientCategory.FORTIFIED_WINE,
        0.17,
        12.0,
        0.5,
        1.03,
        {
            "sweet": 0.5,
            "citrus": 0.5,
            "orchard_fruit": 0.4,
            "floral": 0.35,
            "honey": 0.25,
            "bitter": 0.15,
        },
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
    Spec(
        "Sherry Oloroso",
        IngredientCategory.FORTIFIED_WINE,
        0.19,
        3.0,
        0.4,
        0.99,
        {"nutty": 0.8, "dried_fruit": 0.55, "woody": 0.4, "caramel": 0.3, "umami": 0.2},
    ),
    Spec(
        "Porto Rosso",
        IngredientCategory.FORTIFIED_WINE,
        0.20,
        10.0,
        0.5,
        1.03,
        {
            "sweet": 0.65,
            "berry": 0.5,
            "dried_fruit": 0.55,
            "astringency": 0.25,
            "alcohol_heat": 0.3,
        },
    ),
    # --- Vini e spumanti -------------------------------------------------
    Spec(
        "Prosecco",
        IngredientCategory.WINE,
        0.11,
        1.5,
        0.6,
        0.995,
        {"sour": 0.35, "sweet": 0.15, "orchard_fruit": 0.55, "floral": 0.3, "pungency": 0.4},
    ),
    Spec(
        "Vino Bianco Secco",
        IngredientCategory.WINE,
        0.12,
        0.5,
        0.6,
        0.995,
        {"sour": 0.4, "orchard_fruit": 0.5, "citrus": 0.3, "floral": 0.2},
    ),
    Spec(
        "Vino Rosso",
        IngredientCategory.WINE,
        0.13,
        0.5,
        0.6,
        0.995,
        {"sour": 0.3, "berry": 0.5, "astringency": 0.55, "dried_fruit": 0.3, "woody": 0.2},
    ),
    # --- Bitter, aperitivi e amari ----------------------------------------
    Spec(
        "Campari",
        IngredientCategory.BITTER,
        0.25,
        24.0,
        0.4,
        1.06,
        {"bitter": 0.95, "sweet": 0.5, "citrus": 0.5, "medicinal": 0.4, "floral": 0.2},
    ),
    Spec(
        "Aperol",
        IngredientCategory.BITTER,
        0.11,
        28.0,
        0.4,
        1.09,
        {"bitter": 0.6, "sweet": 0.7, "citrus": 0.7, "medicinal": 0.2},
    ),
    Spec(
        "Select",
        IngredientCategory.BITTER,
        0.17,
        26.0,
        0.4,
        1.07,
        {
            "bitter": 0.75,
            "sweet": 0.55,
            "herbaceous": 0.5,
            "citrus": 0.35,
            "berry": 0.25,
            "medicinal": 0.3,
        },
    ),
    Spec(
        "Cynar",
        IngredientCategory.AMARO,
        0.165,
        20.0,
        0.3,
        1.06,
        {
            "bitter": 0.75,
            "sweet": 0.5,
            "earthy": 0.6,
            "herbaceous": 0.55,
            "caramel": 0.4,
            "medicinal": 0.3,
        },
    ),
    Spec(
        "Fernet-Branca",
        IngredientCategory.AMARO,
        0.39,
        10.0,
        0.2,
        0.98,
        {
            "bitter": 0.95,
            "mint": 0.6,
            "cooling": 0.5,
            "medicinal": 0.8,
            "alcohol_heat": 0.6,
            "anise": 0.25,
            "roasted": 0.3,
        },
    ),
    Spec(
        "Amaro Nonino",
        IngredientCategory.AMARO,
        0.35,
        28.0,
        0.2,
        1.05,
        {
            "bitter": 0.55,
            "sweet": 0.65,
            "caramel": 0.55,
            "orchard_fruit": 0.3,
            "citrus": 0.35,
            "woody": 0.3,
        },
    ),
    Spec(
        "Averna",
        IngredientCategory.AMARO,
        0.29,
        32.0,
        0.3,
        1.08,
        {
            "bitter": 0.55,
            "sweet": 0.75,
            "caramel": 0.65,
            "citrus": 0.35,
            "warm_spice": 0.3,
            "roasted": 0.2,
        },
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
    Spec(
        "Peychaud's Bitters",
        IngredientCategory.BITTER,
        0.35,
        6.0,
        0.0,
        0.97,
        {
            "bitter": 0.75,
            "anise": 0.7,
            "floral": 0.4,
            "berry": 0.3,
            "alcohol_heat": 0.55,
            "warm_spice": 0.25,
        },
    ),
    Spec(
        "Orange Bitters",
        IngredientCategory.BITTER,
        0.40,
        4.0,
        0.0,
        0.97,
        {"bitter": 0.8, "citrus": 0.85, "warm_spice": 0.35, "alcohol_heat": 0.6},
    ),
    # --- Succhi e puree ---------------------------------------------------
    Spec(
        "Succo di Lime",
        IngredientCategory.JUICE,
        0.0,
        1.7,
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
        8.0,
        2.0,
        1.04,
        {"sour": 0.6, "bitter": 0.4, "citrus": 0.85, "floral": 0.2},
    ),
    Spec(
        "Succo d'Arancia",
        IngredientCategory.JUICE,
        0.0,
        10.5,
        0.9,
        1.04,
        {"sweet": 0.6, "sour": 0.35, "citrus": 0.8, "floral": 0.15},
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
    Spec(
        "Succo di Mirtillo Rosso",
        IngredientCategory.JUICE,
        0.0,
        13.0,
        1.0,
        1.06,
        {"sweet": 0.5, "sour": 0.55, "berry": 0.8, "astringency": 0.4},
    ),
    Spec(
        "Succo di Mela",
        IngredientCategory.JUICE,
        0.0,
        11.5,
        0.5,
        1.045,
        {"sweet": 0.65, "sour": 0.3, "orchard_fruit": 0.9},
    ),
    Spec(
        "Succo di Pomodoro",
        IngredientCategory.JUICE,
        0.0,
        5.0,
        0.4,
        1.02,
        {"umami": 0.7, "salty": 0.3, "sour": 0.3, "sweet": 0.25, "earthy": 0.3, "herbaceous": 0.25},
    ),
    Spec(
        "Purea di Frutto della Passione",
        IngredientCategory.JUICE,
        0.0,
        11.0,
        3.0,
        1.05,
        {"sour": 0.65, "sweet": 0.45, "tropical_fruit": 0.95, "floral": 0.2},
    ),
    Spec(
        "Purea di Pesca",
        IngredientCategory.JUICE,
        0.0,
        12.0,
        0.5,
        1.05,
        {"sweet": 0.6, "stone_fruit": 0.95, "sour": 0.2, "floral": 0.15},
    ),
    Spec(
        "Caffè Espresso",
        IngredientCategory.MIXER,
        0.0,
        1.5,
        0.0,
        1.00,
        {"roasted": 0.95, "bitter": 0.6, "caramel": 0.2},
    ),
    # --- Sciroppi e soluzioni ----------------------------------------------
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
        "Sciroppo di Demerara 1:1",
        IngredientCategory.SYRUP,
        0.0,
        50.0,
        0.0,
        1.23,
        {"sweet": 0.95, "caramel": 0.5, "woody": 0.1},
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
        "Sciroppo di Miele 1:1",
        IngredientCategory.SYRUP,
        0.0,
        40.0,
        0.0,
        1.18,
        {"sweet": 1.0, "honey": 0.9, "floral": 0.2},
    ),
    Spec(
        "Sciroppo di Zenzero",
        IngredientCategory.SYRUP,
        0.0,
        45.0,
        0.0,
        1.20,
        {"sweet": 0.9, "pungency": 0.8, "warm_spice": 0.4, "citrus": 0.15},
    ),
    Spec(
        "Granatina",
        IngredientCategory.SYRUP,
        0.0,
        60.0,
        0.5,
        1.28,
        {"sweet": 0.95, "berry": 0.6, "sour": 0.2},
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
    Spec(
        "Soluzione Citrica 6%",
        IngredientCategory.ACID_SOLUTION,
        0.0,
        0.0,
        6.0,
        1.02,
        {"sour": 1.0},
    ),
    Spec(
        "Sciroppo di Sambuco",
        IngredientCategory.SYRUP,
        0.0,
        55.0,
        0.3,
        1.26,
        {"sweet": 0.9, "floral": 0.9, "citrus": 0.2},
    ),
    Spec(
        "Cordial al Lime",
        IngredientCategory.SYRUP,
        0.0,
        45.0,
        1.0,
        1.18,
        {"sweet": 0.8, "sour": 0.5, "citrus": 0.75},
    ),
    Spec(
        "Salsa Worcestershire",
        IngredientCategory.OTHER,
        0.0,
        22.0,
        2.5,
        1.15,
        {"umami": 0.8, "salty": 0.6, "sour": 0.4, "sweet": 0.3, "warm_spice": 0.3, "funky": 0.3},
    ),
    Spec(
        "Tabasco",
        IngredientCategory.OTHER,
        0.0,
        1.0,
        3.0,
        1.0,
        {"pungency": 0.95, "sour": 0.5, "salty": 0.3},
    ),
    # --- Bibite e allungamenti --------------------------------------------
    Spec("Soda", IngredientCategory.MIXER, 0.0, 0.0, 0.0, 1.00, {"pungency": 0.3}),
    Spec(
        "Acqua Tonica",
        IngredientCategory.MIXER,
        0.0,
        8.5,
        0.1,
        1.03,
        {"sweet": 0.5, "bitter": 0.45, "medicinal": 0.5, "pungency": 0.35, "citrus": 0.15},
    ),
    Spec(
        "Ginger Beer",
        IngredientCategory.MIXER,
        0.0,
        10.0,
        0.3,
        1.04,
        {"sweet": 0.55, "pungency": 0.8, "warm_spice": 0.45, "citrus": 0.2},
    ),
    Spec(
        "Ginger Ale",
        IngredientCategory.MIXER,
        0.0,
        8.0,
        0.2,
        1.03,
        {"sweet": 0.55, "pungency": 0.55, "warm_spice": 0.3, "citrus": 0.1},
    ),
    Spec(
        "Cola",
        IngredientCategory.MIXER,
        0.0,
        10.5,
        0.1,
        1.04,
        {"sweet": 0.7, "caramel": 0.7, "warm_spice": 0.3, "citrus": 0.2, "pungency": 0.35},
    ),
)


#: Ricette classiche, con il dosaggio canonico. Sono il banco di prova del
#: solver: si parte da qui, si chiede un target e si guarda di quanto si
#: sposta rispetto alla tradizione.
CLASSICS: tuple[tuple[str, DilutionMethod, ServingIce, str, tuple[tuple[str, float], ...]], ...] = (
    (
        "Daiquiri",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Shake energico con ghiaccio, doppio filtro, coppetta ghiacciata.",
        (("Rum Bianco", 60.0), ("Succo di Lime", 30.0), ("Sciroppo Semplice 1:1", 20.0)),
    ),
    (
        "Negroni",
        DilutionMethod.STIRRED,
        ServingIce.LARGE_CUBE,
        "Mescolare nel mixing glass con ghiaccio, servire su ghiaccio, scorza d'arancia.",
        (("London Dry Gin", 30.0), ("Vermouth Rosso", 30.0), ("Campari", 30.0)),
    ),
    (
        "Margarita",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Shake con ghiaccio, coppetta con bordo di sale a metà.",
        (("Tequila Blanco", 50.0), ("Triple Sec", 20.0), ("Succo di Lime", 25.0)),
    ),
    (
        "Last Word",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
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
        ServingIce.CUBES,
        "Shake con ghiaccio, servire su ghiaccio, angostura in superficie.",
        (("Bourbon", 60.0), ("Succo di Limone", 25.0), ("Sciroppo Semplice 1:1", 20.0)),
    ),
    (
        "Mai Tai",
        DilutionMethod.SHAKEN,
        ServingIce.CRUSHED,
        "Shake, servire su ghiaccio tritato, menta e mezza lime.",
        (
            ("Rum Invecchiato", 45.0),
            ("Triple Sec", 15.0),
            ("Orgeat", 15.0),
            ("Succo di Lime", 22.5),
        ),
    ),
    (
        "Old Fashioned",
        DilutionMethod.STIRRED,
        ServingIce.LARGE_CUBE,
        "Mescolare nel bicchiere con ghiaccio grosso, scorza d'arancia.",
        (("Bourbon", 50.0), ("Sciroppo Semplice 1:1", 7.5), ("Angostura Bitters", 1.8)),
    ),
    (
        "Manhattan",
        DilutionMethod.STIRRED,
        ServingIce.NONE,
        "Mescolare, coppetta, ciliegia.",
        (("Rye Whiskey", 50.0), ("Vermouth Rosso", 20.0), ("Angostura Bitters", 0.9)),
    ),
    (
        "Rob Roy",
        DilutionMethod.STIRRED,
        ServingIce.NONE,
        "Mescolare, coppetta, ciliegia.",
        (("Scotch Blended", 50.0), ("Vermouth Rosso", 20.0), ("Angostura Bitters", 0.9)),
    ),
    (
        "Martini",
        DilutionMethod.STIRRED,
        ServingIce.NONE,
        "Mescolare, coppetta, scorza di limone o oliva.",
        (("London Dry Gin", 60.0), ("Vermouth Dry", 10.0)),
    ),
    (
        "Martinez",
        DilutionMethod.STIRRED,
        ServingIce.NONE,
        "Mescolare, coppetta, scorza d'arancia.",
        (
            ("Old Tom Gin", 45.0),
            ("Vermouth Rosso", 45.0),
            ("Maraschino", 2.5),
            ("Orange Bitters", 0.9),
        ),
    ),
    (
        "Hanky Panky",
        DilutionMethod.STIRRED,
        ServingIce.NONE,
        "Mescolare, coppetta, scorza d'arancia.",
        (("London Dry Gin", 45.0), ("Vermouth Rosso", 45.0), ("Fernet-Branca", 7.5)),
    ),
    (
        "Boulevardier",
        DilutionMethod.STIRRED,
        ServingIce.NONE,
        "Mescolare, coppetta o su ghiaccio, scorza d'arancia.",
        (("Bourbon", 45.0), ("Campari", 30.0), ("Vermouth Rosso", 30.0)),
    ),
    (
        "Sazerac",
        DilutionMethod.STIRRED,
        ServingIce.NONE,
        "Sciacquare il bicchiere con assenzio, mescolare il resto, scorza di limone.",
        (
            ("Rye Whiskey", 50.0),
            ("Sciroppo Semplice 1:1", 7.5),
            ("Peychaud's Bitters", 1.8),
            ("Absinthe", 2.0),
        ),
    ),
    (
        "Americano",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito nel bicchiere con ghiaccio, scorza d'arancia.",
        (("Campari", 30.0), ("Vermouth Rosso", 30.0), ("Soda", 30.0)),
    ),
    (
        "Negroni Sbagliato",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito su ghiaccio, scorza d'arancia.",
        (("Campari", 30.0), ("Vermouth Rosso", 30.0), ("Prosecco", 60.0)),
    ),
    (
        "Aperol Spritz",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito nel calice con ghiaccio, fetta d'arancia.",
        (("Prosecco", 60.0), ("Aperol", 40.0), ("Soda", 20.0)),
    ),
    (
        "Garibaldi",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito nel bicchiere con ghiaccio, fetta d'arancia.",
        (("Campari", 45.0), ("Succo d'Arancia", 150.0)),
    ),
    (
        "Mimosa",
        DilutionMethod.BUILT,
        ServingIce.NONE,
        "Costruito nel flûte, senza ghiaccio.",
        (("Prosecco", 75.0), ("Succo d'Arancia", 75.0)),
    ),
    (
        "Kir",
        DilutionMethod.BUILT,
        ServingIce.NONE,
        "Cassis nel calice, completare con vino bianco.",
        (("Vino Bianco Secco", 90.0), ("Crème de Cassis", 10.0)),
    ),
    (
        "Kir Royale",
        DilutionMethod.BUILT,
        ServingIce.NONE,
        "Cassis nel flûte, completare con spumante.",
        (("Prosecco", 90.0), ("Crème de Cassis", 10.0)),
    ),
    (
        "Gin Tonic",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito su molto ghiaccio, fetta di lime o limone.",
        (("London Dry Gin", 50.0), ("Acqua Tonica", 150.0)),
    ),
    (
        "Moscow Mule",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito su ghiaccio, lime.",
        (("Vodka", 45.0), ("Ginger Beer", 120.0), ("Succo di Lime", 15.0)),
    ),
    (
        "Dark 'n' Stormy",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito su ghiaccio, rum a galleggiare, lime.",
        (("Rum Invecchiato", 60.0), ("Ginger Beer", 100.0), ("Succo di Lime", 10.0)),
    ),
    (
        "Cuba Libre",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito su ghiaccio, spicchio di lime.",
        (("Rum Bianco", 50.0), ("Cola", 120.0), ("Succo di Lime", 10.0)),
    ),
    (
        "Mojito",
        DilutionMethod.BUILT,
        ServingIce.CRUSHED,
        "Menta pestata dolcemente con sciroppo e lime, ghiaccio tritato, completare con soda.",
        (
            ("Rum Bianco", 40.0),
            ("Succo di Lime", 30.0),
            ("Sciroppo Semplice 1:1", 20.0),
            ("Soda", 60.0),
        ),
    ),
    (
        "Caipirinha",
        DilutionMethod.BUILT,
        ServingIce.CRUSHED,
        "Lime pestato con lo zucchero (qui sciroppo), ghiaccio tritato.",
        (("Cachaça", 50.0), ("Succo di Lime", 20.0), ("Sciroppo Semplice 1:1", 20.0)),
    ),
    (
        "Tom Collins",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito su ghiaccio, completare con soda.",
        (
            ("London Dry Gin", 45.0),
            ("Succo di Limone", 30.0),
            ("Sciroppo Semplice 1:1", 15.0),
            ("Soda", 60.0),
        ),
    ),
    (
        "Gin Fizz",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Shake senza soda, filtrare e completare con soda.",
        (
            ("London Dry Gin", 45.0),
            ("Succo di Limone", 30.0),
            ("Sciroppo Semplice 1:1", 10.0),
            ("Soda", 60.0),
        ),
    ),
    (
        "Paloma",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito su ghiaccio, bordo di sale, spicchio di pompelmo.",
        (
            ("Tequila Blanco", 50.0),
            ("Succo di Pompelmo", 40.0),
            ("Succo di Lime", 10.0),
            ("Sciroppo Semplice 1:1", 10.0),
            ("Soda", 60.0),
        ),
    ),
    (
        "Tequila Sunrise",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito su ghiaccio, granatina fatta scendere sul fondo.",
        (("Tequila Blanco", 45.0), ("Succo d'Arancia", 90.0), ("Granatina", 15.0)),
    ),
    (
        "Mint Julep",
        DilutionMethod.BUILT,
        ServingIce.CRUSHED,
        "Menta con sciroppo nel bicchiere, ghiaccio tritato, bourbon, ciuffo di menta.",
        (("Bourbon", 60.0), ("Sciroppo Semplice 1:1", 10.0)),
    ),
    (
        "Bloody Mary",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito su ghiaccio; sale e pepe a piacere, non sono modellati.",
        (
            ("Vodka", 45.0),
            ("Succo di Pomodoro", 90.0),
            ("Succo di Limone", 15.0),
            ("Salsa Worcestershire", 5.0),
            ("Tabasco", 1.0),
        ),
    ),
    (
        "Screwdriver",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito su ghiaccio, fetta d'arancia.",
        (("Vodka", 50.0), ("Succo d'Arancia", 100.0)),
    ),
    (
        "Sea Breeze",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito su ghiaccio, spicchio di lime.",
        (("Vodka", 40.0), ("Succo di Mirtillo Rosso", 120.0), ("Succo di Pompelmo", 30.0)),
    ),
    (
        "Black Russian",
        DilutionMethod.BUILT,
        ServingIce.LARGE_CUBE,
        "Costruito su ghiaccio, bicchiere old fashioned.",
        (("Vodka", 50.0), ("Liquore al Caffè", 20.0)),
    ),
    (
        "Cosmopolitan",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Shake, doppio filtro, coppetta, scorza d'arancia fiammata.",
        (
            ("Vodka", 40.0),
            ("Triple Sec", 15.0),
            ("Succo di Lime", 15.0),
            ("Succo di Mirtillo Rosso", 30.0),
        ),
    ),
    (
        "Espresso Martini",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Shake energico per la schiuma, coppetta, tre chicchi di caffè.",
        (
            ("Vodka", 50.0),
            ("Liquore al Caffè", 10.0),
            ("Caffè Espresso", 30.0),
            ("Sciroppo Semplice 1:1", 10.0),
        ),
    ),
    (
        "Sidecar",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Shake, doppio filtro, coppetta con bordo di zucchero a metà.",
        (("Cognac VSOP", 50.0), ("Triple Sec", 20.0), ("Succo di Limone", 20.0)),
    ),
    (
        "Gimlet",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Shake, doppio filtro, coppetta, spicchio di lime.",
        (("London Dry Gin", 50.0), ("Cordial al Lime", 20.0)),
    ),
    (
        "Southside",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Shake con menta, doppio filtro, coppetta.",
        (("London Dry Gin", 60.0), ("Succo di Lime", 30.0), ("Sciroppo Semplice 1:1", 15.0)),
    ),
    (
        "Bee's Knees",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Shake, doppio filtro, coppetta, scorza di limone.",
        (("London Dry Gin", 50.0), ("Succo di Limone", 25.0), ("Sciroppo di Miele 1:1", 20.0)),
    ),
    (
        "Gold Rush",
        DilutionMethod.SHAKEN,
        ServingIce.LARGE_CUBE,
        "Shake, servire su ghiaccio grosso.",
        (("Bourbon", 60.0), ("Succo di Limone", 22.5), ("Sciroppo di Miele 1:1", 22.5)),
    ),
    (
        "French 75",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Shake degli ingredienti senza spumante, flûte, completare con Prosecco.",
        (
            ("London Dry Gin", 30.0),
            ("Succo di Limone", 15.0),
            ("Sciroppo Semplice 1:1", 10.0),
            ("Prosecco", 60.0),
        ),
    ),
    (
        "Aviation",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Shake, doppio filtro, coppetta, ciliegia.",
        (
            ("London Dry Gin", 45.0),
            ("Maraschino", 15.0),
            ("Crème de Violette", 7.5),
            ("Succo di Limone", 22.5),
        ),
    ),
    (
        "Corpse Reviver No. 2",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Sciacquare la coppetta con assenzio, shake, doppio filtro.",
        (
            ("London Dry Gin", 22.5),
            ("Triple Sec", 22.5),
            ("Lillet Blanc", 22.5),
            ("Succo di Limone", 22.5),
            ("Absinthe", 1.0),
        ),
    ),
    (
        "Paper Plane",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Quattro parti uguali. Shake, doppio filtro, coppetta.",
        (("Bourbon", 22.5), ("Aperol", 22.5), ("Amaro Nonino", 22.5), ("Succo di Limone", 22.5)),
    ),
    (
        "Naked and Famous",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Quattro parti uguali. Shake, doppio filtro, coppetta.",
        (("Mezcal", 22.5), ("Aperol", 22.5), ("Chartreuse Gialla", 22.5), ("Succo di Lime", 22.5)),
    ),
    (
        "Jungle Bird",
        DilutionMethod.SHAKEN,
        ServingIce.CUBES,
        "Shake, servire su ghiaccio, fogliolina d'ananas.",
        (
            ("Rum Invecchiato", 45.0),
            ("Campari", 22.5),
            ("Succo d'Ananas", 45.0),
            ("Succo di Lime", 15.0),
            ("Sciroppo Semplice 1:1", 15.0),
        ),
    ),
    (
        "Penicillin",
        DilutionMethod.SHAKEN,
        ServingIce.LARGE_CUBE,
        "Shake con zenzero, servire su ghiaccio grosso, scotch torbato a galleggiare.",
        (
            ("Scotch Blended", 60.0),
            ("Succo di Limone", 22.5),
            ("Sciroppo di Miele 1:1", 12.5),
            ("Sciroppo di Zenzero", 12.5),
            ("Scotch Islay", 7.5),
        ),
    ),
    (
        "Tommy's Margarita",
        DilutionMethod.SHAKEN,
        ServingIce.CUBES,
        "Shake, servire su ghiaccio.",
        (("Tequila Blanco", 60.0), ("Succo di Lime", 30.0), ("Sciroppo d'Agave", 15.0)),
    ),
    (
        "Hemingway Daiquiri",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Shake, doppio filtro, coppetta.",
        (
            ("Rum Bianco", 60.0),
            ("Succo di Lime", 15.0),
            ("Succo di Pompelmo", 40.0),
            ("Maraschino", 15.0),
        ),
    ),
    (
        "Pisco Sour",
        DilutionMethod.SHAKEN,
        ServingIce.NONE,
        "Shake, coppetta, angostura in superficie; l'albume non è modellato.",
        (("Pisco", 45.0), ("Succo di Lime", 30.0), ("Sciroppo Semplice 1:1", 20.0)),
    ),
    (
        "Amaretto Sour",
        DilutionMethod.SHAKEN,
        ServingIce.CUBES,
        "Shake, servire su ghiaccio, ciliegia.",
        (("Amaretto", 45.0), ("Succo di Limone", 30.0), ("Sciroppo Semplice 1:1", 10.0)),
    ),
    (
        "Long Island Iced Tea",
        DilutionMethod.SHAKEN,
        ServingIce.CUBES,
        "Shake senza cola, servire su ghiaccio e completare con cola.",
        (
            ("Vodka", 15.0),
            ("London Dry Gin", 15.0),
            ("Rum Bianco", 15.0),
            ("Tequila Blanco", 15.0),
            ("Triple Sec", 15.0),
            ("Succo di Limone", 25.0),
            ("Sciroppo Semplice 1:1", 30.0),
            ("Cola", 20.0),
        ),
    ),
    (
        "Bellini",
        DilutionMethod.BUILT,
        ServingIce.NONE,
        "Purea di pesca nel flûte, completare con Prosecco e mescolare piano.",
        (("Prosecco", 100.0), ("Purea di Pesca", 50.0)),
    ),
    (
        "Hugo",
        DilutionMethod.BUILT,
        ServingIce.CUBES,
        "Costruito su ghiaccio, menta e fetta di lime.",
        (("Prosecco", 100.0), ("Sciroppo di Sambuco", 20.0), ("Soda", 30.0)),
    ),
    (
        "Rusty Nail",
        DilutionMethod.BUILT,
        ServingIce.LARGE_CUBE,
        "Costruito su ghiaccio grosso, scorza di limone.",
        (("Scotch Blended", 45.0), ("Drambuie", 25.0)),
    ),
)


#: Ricette del seed la cui dose è stata corretta dopo la prima versione.
#: Il seed riallinea dosi e istruzioni solo di queste: allinearle tutte
#: sovrascriverebbe i ribilanciamenti che l'utente ha salvato col solver.
REVISED: frozenset[str] = frozenset({"Gimlet", "Bloody Mary"})


async def rename_legacy(repository: SqlAlchemyIngredientRepository) -> None:
    for old_name, new_name in RENAMED.items():
        legacy = await repository.get_by_name(old_name)
        if legacy is None or await repository.get_by_name(new_name) is not None:
            continue
        await repository.save(replace(legacy, name=new_name))
        print(f"Rinominato: {old_name} -> {new_name}")


#: Profili fisici che una revisione dei dati ha sostituito, per nome.
#:
#: Il seed salta gli ingredienti già presenti, quindi correggere un valore in
#: `BAR` non toccherebbe un database già popolato. Qui si ricorda il valore
#: **precedente**: il seed riallinea un ingrediente solo se il suo profilo
#: salvato coincide ancora con quello, cioè se nessuno l'ha ritoccato a mano.
#: Una dispensa personalizzata non viene sovrascritta.
#:
#: Revisione "Brix = solo zuccheri": le letture rifrattometriche contavano
#: anche gli acidi e gonfiavano il dolce dei succhi più acidi.
SUPERSEDED_PROFILES: dict[str, PhysicalProfile] = {
    "Succo di Lime": PhysicalProfile(density_g_ml=1.03, brix=7.5, acidity=6.0, abv=0.0),
    "Succo di Pompelmo": PhysicalProfile(density_g_ml=1.04, brix=9.0, acidity=2.0, abv=0.0),
    "Succo di Mirtillo Rosso": PhysicalProfile(density_g_ml=1.06, brix=14.0, acidity=1.0, abv=0.0),
    "Purea di Frutto della Passione": PhysicalProfile(
        density_g_ml=1.05, brix=14.0, acidity=3.0, abv=0.0
    ),
}


def physical_profile_of(spec: Spec) -> PhysicalProfile:
    return PhysicalProfile(
        density_g_ml=spec.density, brix=spec.brix, acidity=spec.acidity, abv=spec.abv
    )


def revised_profile(stored: Ingredient, spec: Spec) -> PhysicalProfile | None:
    """Il profilo corretto da applicare, o `None` se non c'è nulla da riallineare.

    Riallinea solo un ingrediente che porta ancora il valore sostituito dalla
    revisione: se l'utente l'ha modificato, quel dato è suo.
    """
    superseded = SUPERSEDED_PROFILES.get(spec.name)
    if superseded is None or stored.physical_profile != superseded:
        return None
    return physical_profile_of(spec)


async def seed_ingredients(session: AsyncSession) -> dict[str, Ingredient]:
    repository = SqlAlchemyIngredientRepository(session)
    catalogue: dict[str, Ingredient] = {}
    created = 0
    realigned = 0

    await rename_legacy(repository)

    for spec in BAR:
        existing = await repository.get_by_name(spec.name)
        if existing is not None:
            corrected = revised_profile(existing, spec)
            if corrected is not None:
                existing = await repository.save(replace(existing, physical_profile=corrected))
                realigned += 1
                print(f"Riallineato: {spec.name}")
            catalogue[spec.name] = existing
            continue

        ingredient = Ingredient(
            id=str(uuid.uuid4()),
            name=spec.name,
            category=spec.category,
            physical_profile=physical_profile_of(spec),
            flavor_profile=FlavorProfile.from_descriptors(**spec.flavor),
        )
        catalogue[spec.name] = await repository.add(ingredient)
        created += 1

    print(
        f"Ingredienti: {created} creati, {len(BAR) - created} già presenti"
        f" ({realigned} riallineati)."
    )
    return catalogue


#: Bicchiere di servizio dei classici, per nome. È una tabella a parte e non
#: un sesto elemento di `CLASSICS` perché il bicchiere è facoltativo nel
#: dominio: una ricetta senza voce qui resta valida, senza bicchiere.
CLASSIC_GLASSES: dict[str, GlassType] = {
    "Daiquiri": GlassType.COUPE,
    "Margarita": GlassType.COUPE,
    "Last Word": GlassType.COUPE,
    "Sidecar": GlassType.COUPE,
    "Gimlet": GlassType.COUPE,
    "Southside": GlassType.COUPE,
    "Bee's Knees": GlassType.COUPE,
    "Aviation": GlassType.COUPE,
    "Corpse Reviver No. 2": GlassType.COUPE,
    "Paper Plane": GlassType.COUPE,
    "Naked and Famous": GlassType.COUPE,
    "Hemingway Daiquiri": GlassType.MARTINI,
    "Pisco Sour": GlassType.COUPE,
    "Manhattan": GlassType.COUPE,
    "Rob Roy": GlassType.COUPE,
    "Martinez": GlassType.COUPE,
    "Hanky Panky": GlassType.COUPE,
    "Boulevardier": GlassType.COUPE,
    "Martini": GlassType.MARTINI,
    "Cosmopolitan": GlassType.MARTINI,
    "Espresso Martini": GlassType.MARTINI,
    "Negroni": GlassType.ROCKS,
    "Old Fashioned": GlassType.ROCKS,
    "Whiskey Sour": GlassType.ROCKS,
    "Gold Rush": GlassType.DOUBLE_ROCKS,
    "Penicillin": GlassType.DOUBLE_ROCKS,
    "Tommy's Margarita": GlassType.ROCKS,
    "Amaretto Sour": GlassType.ROCKS,
    "Sazerac": GlassType.ROCKS,
    "Black Russian": GlassType.ROCKS,
    "Negroni Sbagliato": GlassType.ROCKS,
    "Americano": GlassType.ROCKS,
    "Caipirinha": GlassType.ROCKS,
    "Mai Tai": GlassType.DOUBLE_ROCKS,
    "Jungle Bird": GlassType.DOUBLE_ROCKS,
    "Garibaldi": GlassType.HIGHBALL,
    "Dark 'n' Stormy": GlassType.HIGHBALL,
    "Cuba Libre": GlassType.HIGHBALL,
    "Mojito": GlassType.HIGHBALL,
    "Gin Fizz": GlassType.HIGHBALL,
    "Paloma": GlassType.HIGHBALL,
    "Tequila Sunrise": GlassType.HIGHBALL,
    "Bloody Mary": GlassType.HIGHBALL,
    "Screwdriver": GlassType.HIGHBALL,
    "Sea Breeze": GlassType.HIGHBALL,
    "Tom Collins": GlassType.COLLINS,
    "Long Island Iced Tea": GlassType.COLLINS,
    "Moscow Mule": GlassType.COPPER_MUG,
    "Aperol Spritz": GlassType.BALLOON,
    "Gin Tonic": GlassType.BALLOON,
    "Kir": GlassType.WINE,
    "Mimosa": GlassType.FLUTE,
    "Kir Royale": GlassType.FLUTE,
    "French 75": GlassType.FLUTE,
    "Mint Julep": GlassType.OTHER,
    "Bellini": GlassType.FLUTE,
    "Hugo": GlassType.WINE,
    "Rusty Nail": GlassType.ROCKS,
}


#: Classici spostati di bicchiere da una revisione, con il bicchiere di
#: prima. Con il cubo grosso contato per il suo volume (125 ml, ADR-0013),
#: Penicillin e Gold Rush non entrano nel tumbler basso generico da 300 ml:
#: si servono nel doppio, come fanno molti bar. Il seed sposta solo le
#: ricette che hanno ancora il bicchiere di prima: una scelta fatta a mano
#: resta.
SUPERSEDED_GLASSES: dict[str, GlassType] = {
    "Gold Rush": GlassType.ROCKS,
    "Penicillin": GlassType.ROCKS,
}

# Kir non compare: è vino bianco e cassis, senza bollicine né amaro, e la
# famiglia è facoltativa proprio per non forzare un'etichetta falsa. Nessun
# classico del catalogo è emulsionato (albume, panna): `EMULSIFIED` resta
# vuota finché non entra una ricetta che lo giustifichi.
CLASSIC_FAMILIES: dict[str, RecipeFamily] = {
    "Daiquiri": RecipeFamily.SOUR,
    "Margarita": RecipeFamily.SOUR,
    "Last Word": RecipeFamily.SOUR,
    "Whiskey Sour": RecipeFamily.SOUR,
    "Sidecar": RecipeFamily.SOUR,
    "Gimlet": RecipeFamily.SOUR,
    "Southside": RecipeFamily.SOUR,
    "Bee's Knees": RecipeFamily.SOUR,
    "Gold Rush": RecipeFamily.SOUR,
    "Aviation": RecipeFamily.SOUR,
    "Corpse Reviver No. 2": RecipeFamily.SOUR,
    "Paper Plane": RecipeFamily.SOUR,
    "Naked and Famous": RecipeFamily.SOUR,
    "Penicillin": RecipeFamily.SOUR,
    "Tommy's Margarita": RecipeFamily.SOUR,
    "Hemingway Daiquiri": RecipeFamily.SOUR,
    "Pisco Sour": RecipeFamily.SOUR,
    "Amaretto Sour": RecipeFamily.SOUR,
    "Cosmopolitan": RecipeFamily.SOUR,
    "Gin Fizz": RecipeFamily.SOUR,
    "Caipirinha": RecipeFamily.SOUR,
    "Negroni": RecipeFamily.SPIRIT_FORWARD,
    "Old Fashioned": RecipeFamily.SPIRIT_FORWARD,
    "Manhattan": RecipeFamily.SPIRIT_FORWARD,
    "Rob Roy": RecipeFamily.SPIRIT_FORWARD,
    "Martini": RecipeFamily.SPIRIT_FORWARD,
    "Martinez": RecipeFamily.SPIRIT_FORWARD,
    "Hanky Panky": RecipeFamily.SPIRIT_FORWARD,
    "Boulevardier": RecipeFamily.SPIRIT_FORWARD,
    "Sazerac": RecipeFamily.SPIRIT_FORWARD,
    "Black Russian": RecipeFamily.SPIRIT_FORWARD,
    "Rusty Nail": RecipeFamily.SPIRIT_FORWARD,
    "Mint Julep": RecipeFamily.SPIRIT_FORWARD,
    "Espresso Martini": RecipeFamily.SPIRIT_FORWARD,
    "Gin Tonic": RecipeFamily.HIGHBALL,
    "Moscow Mule": RecipeFamily.HIGHBALL,
    "Dark 'n' Stormy": RecipeFamily.HIGHBALL,
    "Cuba Libre": RecipeFamily.HIGHBALL,
    "Mojito": RecipeFamily.HIGHBALL,
    "Tom Collins": RecipeFamily.HIGHBALL,
    "Paloma": RecipeFamily.HIGHBALL,
    "Tequila Sunrise": RecipeFamily.HIGHBALL,
    "Bloody Mary": RecipeFamily.HIGHBALL,
    "Screwdriver": RecipeFamily.HIGHBALL,
    "Sea Breeze": RecipeFamily.HIGHBALL,
    "Garibaldi": RecipeFamily.HIGHBALL,
    "Long Island Iced Tea": RecipeFamily.HIGHBALL,
    "Mai Tai": RecipeFamily.TROPICAL,
    "Jungle Bird": RecipeFamily.TROPICAL,
    "Aperol Spritz": RecipeFamily.SPRITZ,
    "Hugo": RecipeFamily.SPRITZ,
    "Americano": RecipeFamily.SPRITZ,
    "Negroni Sbagliato": RecipeFamily.SPRITZ,
    "French 75": RecipeFamily.SPARKLING,
    "Mimosa": RecipeFamily.SPARKLING,
    "Kir Royale": RecipeFamily.SPARKLING,
    "Bellini": RecipeFamily.SPARKLING,
}


async def seed_recipes(session: AsyncSession, catalogue: dict[str, Ingredient]) -> None:
    repository = SqlAlchemyRecipeRepository(session)
    existing = {recipe.name: recipe for recipe in await repository.list(limit=500)}
    created = 0
    realigned = 0

    for name, method, serving_ice, instructions, doses in CLASSICS:
        stored = existing.get(name)
        if stored is not None:
            # Le ricette create prima dell'introduzione di `serving_ice`
            # hanno il valore di migrazione (`NONE`): il seed le riallinea,
            # così un database già popolato non resta con servizi sbagliati.
            if name in REVISED:
                await repository.save(
                    replace(
                        stored,
                        instructions=instructions,
                        ingredients=tuple(
                            RecipeIngredient(
                                ingredient=catalogue[ingredient_name], volume_ml=volume
                            )
                            for ingredient_name, volume in doses
                        ),
                    )
                )
                stored = await repository.get(stored.id) or stored
            glass = CLASSIC_GLASSES.get(name)
            family = CLASSIC_FAMILIES.get(name)
            # Bicchiere e famiglia sono facoltativi: il seed li imposta solo
            # dove mancano, così non sovrascrive una scelta fatta a mano. Fa
            # eccezione un bicchiere che una revisione ha sostituito, finché
            # la ricetta ha ancora quello.
            moved = stored.glass is not None and SUPERSEDED_GLASSES.get(name) is stored.glass
            if (
                stored.serving_ice is not serving_ice
                or (stored.glass is None and glass is not None)
                or (stored.family is None and family is not None)
                or moved
            ):
                await repository.save(
                    replace(
                        stored,
                        serving_ice=serving_ice,
                        glass=glass if moved or stored.glass is None else stored.glass,
                        family=stored.family if stored.family is not None else family,
                    )
                )
                realigned += 1
            continue
        await repository.add(
            Recipe(
                id=str(uuid.uuid4()),
                name=name,
                dilution_method=method,
                serving_ice=serving_ice,
                glass=CLASSIC_GLASSES.get(name),
                family=CLASSIC_FAMILIES.get(name),
                instructions=instructions,
                ingredients=tuple(
                    RecipeIngredient(ingredient=catalogue[ingredient_name], volume_ml=volume)
                    for ingredient_name, volume in doses
                ),
            )
        )
        created += 1

    print(
        f"Ricette: {created} create, {len(CLASSICS) - created} già presenti "
        f"({realigned} con ghiaccio, bicchiere o famiglia riallineati)."
    )


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
