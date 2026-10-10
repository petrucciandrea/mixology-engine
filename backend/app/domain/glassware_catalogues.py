"""Cataloghi di bicchieri: linee reali con le misure delle loro schede.

Non esiste uno standard normativo per i bicchieri da bar (l'unico è il
calice da degustazione ISO 3591, uno strumento d'analisi). Lo standard di
fatto sono le linee professionali dei produttori: qui ne stanno tre di
fascia alta, diffuse nei cocktail bar italiani, più un catalogo generico
che copre ogni tipo con misure tipiche (ADR-0013).

Ogni bicchiere riporta le misure **come pubblicate** (capienza a colmo,
altezza totale, diametro massimo esterni) e la fonte. Le schede vengono
quasi sempre dai distributori, non dai produttori, che raramente
pubblicano le misure: dove le fonti discordano si è presa quella che
concorda con le altre. La profondità della coppa non si inserisce mai: la
ricava `GlassModel` dalla capienza (vedi `serving_geometry`).

Un tipo che la linea non produce non c'è, invece di prendere misure
inventate: per quello resta il catalogo generico. Lo stesso vale per le
schede incoerenti (capienza che non sta nelle misure dichiarate): il
bicchiere resta fuori invece di essere aggiustato.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from .enums import GlassType, Glassware
from .serving_geometry import GlassModel, GlassShape

_T = GlassShape


@dataclass(frozen=True, slots=True)
class GlasswareCatalogue:
    """Una linea di bicchieri: chi la produce e quali bicchieri contiene."""

    glassware: Glassware
    name: str
    maker: str
    description: str
    models: Mapping[GlassType, GlassModel]

    def model(self, glass: GlassType) -> GlassModel | None:
        return self.models.get(glass)


def _catalogue(
    glassware: Glassware, name: str, maker: str, description: str, *models: GlassModel
) -> GlasswareCatalogue:
    return GlasswareCatalogue(
        glassware=glassware,
        name=name,
        maker=maker,
        description=description,
        models=MappingProxyType({model.glass: model for model in models}),
    )


_TYPICAL = "Misure tipiche di settore, non di un prodotto (ADR-0013)"

GENERIC: Final = _catalogue(
    Glassware.GENERIC,
    "Generico",
    "—",
    "Misure tipiche per ogni tipo di bicchiere, non di un prodotto specifico. "
    "Copre anche i tipi che le linee di marca non producono.",
    GlassModel(GlassType.COUPE, "Coppa", 210.0, 150.0, 105.0, _T.COUPE, _TYPICAL),
    GlassModel(GlassType.MARTINI, "Coppa Martini", 240.0, 180.0, 115.0, _T.CONE, _TYPICAL),
    GlassModel(GlassType.NICK_AND_NORA, "Nick & Nora", 160.0, 150.0, 74.0, _T.BELL, _TYPICAL),
    GlassModel(GlassType.ROCKS, "Tumbler basso", 300.0, 90.0, 84.0, _T.TUMBLER, _TYPICAL),
    GlassModel(GlassType.DOUBLE_ROCKS, "Doppio tumbler", 400.0, 100.0, 92.0, _T.TUMBLER, _TYPICAL),
    GlassModel(GlassType.HIGHBALL, "Highball", 350.0, 150.0, 72.0, _T.TUMBLER, _TYPICAL),
    GlassModel(GlassType.COLLINS, "Collins", 400.0, 175.0, 66.0, _T.TUMBLER, _TYPICAL),
    GlassModel(GlassType.FLUTE, "Flûte", 200.0, 225.0, 66.0, _T.FLUTE, _TYPICAL),
    GlassModel(GlassType.WINE, "Calice", 350.0, 215.0, 84.0, _T.TULIP, _TYPICAL),
    GlassModel(GlassType.BALLOON, "Balloon", 650.0, 205.0, 108.0, _T.BALLOON, _TYPICAL),
    GlassModel(
        GlassType.COPPER_MUG,
        "Mug di rame",
        450.0,
        95.0,
        90.0,
        _T.TUMBLER,
        _TYPICAL,
        base_ratio=1.0,
    ),
    GlassModel(GlassType.TIKI, "Tiki mug", 450.0, 160.0, 82.0, _T.TIKI, _TYPICAL),
    GlassModel(GlassType.HURRICANE, "Hurricane", 450.0, 220.0, 85.0, _T.HURRICANE, _TYPICAL),
    GlassModel(GlassType.SHOT, "Bicchierino", 50.0, 60.0, 45.0, _T.TUMBLER, _TYPICAL),
)

SCHOTT_ZWIESEL: Final = _catalogue(
    Glassware.SCHOTT_ZWIESEL,
    "Schott Zwiesel",
    "Zwiesel Kristallglas (Germania)",
    "Bar Selection, la linea disegnata con Charles Schumann: lo standard dei "
    "bartender, in cristallo Tritan. Calice Ivento.",
    GlassModel(
        GlassType.COUPE,
        "Basic Bar Selection Cocktail 88",
        259.0,
        129.0,
        101.0,
        _T.COUPE,
        "https://www.esmeyer-shop.de/en/schott-zwiesel-coctailschale-basic-bar-selection-chschumann-88-shape-8750",
    ),
    GlassModel(
        GlassType.MARTINI,
        "Basic Bar Selection Martini Contemporary 87",
        226.0,
        129.0,
        102.0,
        _T.CONE,
        "https://www.esmeyer-shop.de/en/schott-zwiesel-martini-contemporary-basic-bar-selection-by-chschumann-87-shape-8750",
    ),
    GlassModel(
        GlassType.NICK_AND_NORA,
        "Bar Selection Nick & Nora 147",
        167.0,
        147.0,
        73.0,
        _T.BELL,
        "https://www.esmeyer-shop.de/en/stielglas-bar-selection-147-nick-nora-0-167-liter-hoehe-147mm-durchmesser-73mm-167ml-tritan-kristallglas-klar-form-8832-schott",
    ),
    GlassModel(
        GlassType.ROCKS,
        "Bar Selection Age Whisky 60",
        294.0,
        100.0,
        82.0,
        _T.TUMBLER,
        "https://www.esmeyer-shop.de/en/whiskyglas-bar-selection-age-60-0-294-liter-hoehe-100mm-durchmesser-82mm-294ml-tritan-kristallglas-klar-form-9140-schott-zwiesel",
    ),
    GlassModel(
        GlassType.DOUBLE_ROCKS,
        "Basic Bar Selection Whisky 60",
        356.0,
        92.0,
        87.5,
        _T.TUMBLER,
        "https://www.esmeyer-shop.de/en/schott-zwiesel-tumbler-whisky-basic-bar-selection-by-chschumann-60-shape-8750",
    ),
    GlassModel(
        GlassType.HIGHBALL,
        "Stage Longdrink 79",
        440.0,
        150.0,
        76.0,
        _T.TUMBLER,
        "https://www.united-tables.com/products/glassware/restaurant-bar-glasses/aperol-glasses/676-stage-longdrink/",
    ),
    GlassModel(
        GlassType.COLLINS,
        "Basic Bar Selection Longdrink 79",
        366.0,
        156.0,
        70.0,
        _T.TUMBLER,
        "https://www.united-tables.com/products/glassware/restaurant-bar-glasses/long-drink-glasses/642-basic-bar-selection-longdrink/",
    ),
    GlassModel(
        GlassType.FLUTE,
        "Bar Selection Premium Sparkling Wine 772",
        384.0,
        232.0,
        86.0,
        _T.TULIP,
        "https://www.culinaris.de/en/Schott-Zwiesel-Bar-Special-Premium-Sparkling-Wine-Glass-Set-of-4/5886",
    ),
    GlassModel(
        GlassType.WINE,
        "Ivento White Wine 2",
        349.0,
        208.0,
        77.0,
        _T.TULIP,
        "https://www.esmeyer-shop.de/en/schott-ivento-white-wine-glass-capacity-035-l-height-208-mm-diameter-77-mm-by-schott-zwiesel-made-in-germany",
    ),
    GlassModel(
        GlassType.BALLOON,
        "Bar Selection Gin Tonic 80",
        710.0,
        178.0,
        116.0,
        _T.BALLOON,
        "https://www.ballantynes.co.nz/home/dining/glassware/stemware/schott-zwiesel-gin-and-tonic-glasses---set-of-4/2383352.html",
    ),
    GlassModel(
        GlassType.HURRICANE,
        "Bar Special Hurricane 300",
        530.0,
        183.0,
        89.0,
        _T.HURRICANE,
        "https://www.united-tables.com/products/glassware/restaurant-bar-glasses/cocktail-glasses/813-bar-special-hurricane/",
    ),
    GlassModel(
        GlassType.SHOT,
        "Bar Selection Show Shot 35",
        78.0,
        60.0,
        52.0,
        _T.TUMBLER,
        "https://www.zwieselfortessa.com/hospitality/products/glassware/restaurant-bar-glasses/shot-glasses/1403-bar-selection-show-shot-glass/",
    ),
)

LUIGI_BORMIOLI: Final = _catalogue(
    Glassware.LUIGI_BORMIOLI,
    "Luigi Bormioli",
    "Luigi Bormioli (Parma)",
    "Mixology, la linea da cocktail bar in vetro SON.hyx; Bach per i long "
    "drink, Atelier e Magnifico per flûte e calice. La più diffusa "
    "nell'HORECA italiano.",
    GlassModel(
        GlassType.COUPE,
        "Mixology Coupe",
        225.0,
        140.0,
        95.0,
        _T.COUPE,
        "https://www.hospitalitysuperstore.com.au/product/mixology-coupe-cocktail-glass-225ml-luigi-bormioli/",
    ),
    GlassModel(
        GlassType.MARTINI,
        "Mixology Martini",
        215.0,
        172.0,
        104.0,
        _T.CONE,
        "https://checkout.binuns.co.za/products/mixology-martini-glasses-set-of-4",
    ),
    GlassModel(
        GlassType.NICK_AND_NORA,
        "Mixology Nick & Nora",
        150.0,
        148.0,
        70.0,
        _T.BELL,
        "https://www.binuns.co.za/mixology-nick-nora-cocktail-glasses-set-of-6.html",
    ),
    GlassModel(
        GlassType.ROCKS,
        "Mixology Textures Whisky",
        380.0,
        97.0,
        87.0,
        _T.TUMBLER,
        "https://www.binuns.co.za/mixology-textures-whiskey-glasses-set-of-6.html",
    ),
    GlassModel(
        GlassType.DOUBLE_ROCKS,
        "Mixology Cocktail Club D.O.F.",
        400.0,
        102.0,
        95.0,
        _T.TUMBLER,
        "https://www.chefsupplies.ca/products/luigi-bormioli-13-5-oz-mixology-italian-premium-cocktail-club-d-o-f-whiskey-glass-13252",
    ),
    GlassModel(
        GlassType.HIGHBALL,
        "Mixology Textures Hi-Ball",
        480.0,
        158.0,
        75.0,
        _T.TUMBLER,
        "https://www.binuns.co.za/mixology-textures-480ml-hiball-glasses-set-of-4.html",
    ),
    GlassModel(
        GlassType.COLLINS,
        "Bach Hi-Ball",
        480.0,
        160.0,
        72.0,
        _T.TUMBLER,
        "https://www.hospitalitysuperstore.com.au/product/hi-ball-bach-480ml-luigi-bormioli",
    ),
    GlassModel(
        GlassType.FLUTE,
        "Atelier Flûte",
        281.0,
        254.0,
        76.0,
        _T.FLUTE,
        "https://www.webstaurantstore.com/luigi-bormioli-08748-07-atelier-9-25-oz-champagne-flute-case/5670874807.html",
    ),
    GlassModel(
        GlassType.WINE,
        "Magnifico Calice Small",
        350.0,
        230.0,
        82.0,
        _T.TULIP,
        "https://www.yeppon.it/products/cf-6-cal-magnifico-921502",
    ),
    GlassModel(
        GlassType.BALLOON,
        "Mixology Spanish Gin & Tonic",
        800.0,
        205.0,
        119.0,
        _T.BALLOON,
        "https://www.lusini.com/en/pdp/208405",
    ),
    GlassModel(
        GlassType.SHOT,
        "Mixology Shot",
        67.0,
        89.0,
        38.0,
        _T.TUMBLER,
        "https://www.webstaurantstore.com/shot-2-25oz-mixology-2dz-case/5671272201.html",
    ),
)

NUDE: Final = _catalogue(
    Glassware.NUDE,
    "Nude",
    "Nude Glass (Turchia)",
    "Savage, la linea disegnata con Rémy Savage, Refine e Stem Zero: cristallo "
    "senza piombo e design contemporaneo, molto usata nei cocktail bar.",
    GlassModel(
        GlassType.COUPE,
        "Savage Coupe",
        222.0,
        175.0,
        108.0,
        _T.COUPE,
        "https://argo.webstaurantstore.com/documents/pdf/brochure/nude_savage.pdf",
    ),
    GlassModel(
        GlassType.MARTINI,
        "Savage Coupetini",
        170.0,
        166.0,
        100.0,
        _T.CONE,
        "https://hospitalitysuperstore.com.au/product/coupetini-170ml-savage-by-nude-eta-january-2023",
    ),
    GlassModel(
        GlassType.NICK_AND_NORA,
        "Refine Nick & Nora",
        170.0,
        150.0,
        76.0,
        _T.BELL,
        "https://www.hospitalitysuperstore.com.au/product/cocktail-refine-170ml-nude-nick-nora",
    ),
    # Savage è a pareti dritte e fondo spesso: il fondo è largo quanto la bocca.
    GlassModel(
        GlassType.ROCKS,
        "Savage Old Fashioned",
        260.0,
        82.0,
        82.0,
        _T.TUMBLER,
        "https://hospitalitysuperstore.com.au/product/water-260ml-savage-by-nude",
        base_ratio=1.0,
    ),
    GlassModel(
        GlassType.DOUBLE_ROCKS,
        "Savage Whisky",
        390.0,
        89.0,
        83.0,
        _T.TUMBLER,
        "https://vinumdesign.com/en/products/verre-a-whisky-tumbler-savage-nude",
        base_ratio=1.0,
    ),
    GlassModel(
        GlassType.HIGHBALL,
        "Savage Highball",
        330.0,
        146.0,
        68.0,
        _T.TUMBLER,
        "https://www.advantage-catering-equipment.co.uk/products/nude-savage-highball-glasses-330ml-pack-of-6",
        base_ratio=1.0,
    ),
    GlassModel(
        GlassType.FLUTE,
        "Stem Zero Flute",
        300.0,
        257.0,
        62.0,
        _T.FLUTE,
        "https://eu.nudeglass.com/products/stem-zero-flute-champagne-glass",
    ),
    GlassModel(
        GlassType.WINE,
        "Stem Zero Delicate White Wine",
        450.0,
        229.5,
        87.0,
        _T.TULIP,
        "https://eu.nudeglass.com/products/stem-zero-delicate-white-wine-glass",
    ),
)

CATALOGUES: Final[Mapping[Glassware, GlasswareCatalogue]] = MappingProxyType(
    {
        catalogue.glassware: catalogue
        for catalogue in (GENERIC, LUIGI_BORMIOLI, SCHOTT_ZWIESEL, NUDE)
    }
)


def glass_model(glassware: Glassware, glass: GlassType | None) -> GlassModel | None:
    """Il bicchiere `glass` nel catalogo `glassware`, se c'è.

    `None` anche per "nessun bicchiere" e per `OTHER`, che non ha misure in
    nessun catalogo.
    """
    if glass is None:
        return None
    return CATALOGUES[glassware].model(glass)
