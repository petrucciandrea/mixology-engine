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


class ServingIce(str, Enum):
    """Ghiaccio nel bicchiere di servizio, o sua assenza.

    È una proprietà del *servizio*, distinta dalla `DilutionMethod`: il
    ghiaccio usato per raffreddare nel shaker o nel mixing glass viene
    scartato, quello nel bicchiere resta e continua a diluire. Un Daiquiri
    è shakerato e servito senza ghiaccio, un Whiskey Sour è shakerato e
    servito su cubetti: stessa diluizione di preparazione, servizio diverso.

    Assenza e tipo sono un solo enum (`NONE` incluso) perché due campi
    separati ammetterebbero uno stato illegale — "senza ghiaccio" con un
    tipo di ghiaccio — che così non si può nemmeno rappresentare.
    """

    NONE = "NONE"
    CUBES = "CUBES"
    LARGE_CUBE = "LARGE_CUBE"
    CRUSHED = "CRUSHED"


class GlassType(str, Enum):
    """Bicchiere in cui il drink viene servito.

    È una proprietà del *servizio* come `ServingIce`, ma **opzionale**: una
    ricetta può non dichiararlo, e in quel caso non esiste un limite di
    capienza. `OTHER` esiste per i bicchieri fuori elenco e, non avendo una
    capienza nota, non pone alcun limite (vedi `domain/services/glassware`).

    Il bicchiere non entra nella diluizione: ne descrive il contenitore,
    non la termodinamica. Entra nel solver solo come tetto al volume.
    """

    COUPE = "COUPE"
    MARTINI = "MARTINI"
    NICK_AND_NORA = "NICK_AND_NORA"
    ROCKS = "ROCKS"
    DOUBLE_ROCKS = "DOUBLE_ROCKS"
    HIGHBALL = "HIGHBALL"
    COLLINS = "COLLINS"
    FLUTE = "FLUTE"
    WINE = "WINE"
    BALLOON = "BALLOON"
    COPPER_MUG = "COPPER_MUG"
    TIKI = "TIKI"
    HURRICANE = "HURRICANE"
    SHOT = "SHOT"
    OTHER = "OTHER"


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
