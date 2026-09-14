"""Enumerazioni del dominio.

Vivono in un modulo separato dalle entità perché sono vocabolario
condiviso: le usano entità, servizi di dominio, mapper di persistenza e
DTO dell'API. Tenerle qui evita import circolari fra `entities` e i
servizi che le consumano.
"""

from __future__ import annotations

from enum import Enum


class DilutionMethod(str, Enum):
    """Tecnica di preparazione, da cui dipende la diluizione da ghiaccio.

    Il modello termodinamico di Dave Arnold associa a ciascuna tecnica una
    curva di diluizione diversa, perché variano superficie di scambio,
    energia immessa e tempo di contatto con il ghiaccio.
    """

    SHAKEN = "SHAKEN"
    STIRRED = "STIRRED"
    BUILT = "BUILT"


class IngredientCategory(str, Enum):
    """Famiglia merceologica dell'ingrediente.

    Non è una tassonomia organolettica (quella è il `FlavorProfile`): serve
    a vincolare il solver per categoria — ad esempio "almeno 40 ml di
    distillato", "al massimo 25 ml di sciroppo" — e a rendere leggibili le
    ricette. `OTHER` esiste per non bloccare l'inserimento di ingredienti
    che non ricadono nelle famiglie previste.
    """

    SPIRIT = "SPIRIT"
    LIQUEUR = "LIQUEUR"
    FORTIFIED_WINE = "FORTIFIED_WINE"
    WINE = "WINE"
    BITTER = "BITTER"
    AMARO = "AMARO"
    JUICE = "JUICE"
    SYRUP = "SYRUP"
    ACID_SOLUTION = "ACID_SOLUTION"
    MIXER = "MIXER"
    WATER = "WATER"
    OTHER = "OTHER"
