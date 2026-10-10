"""DTO dei cataloghi di bicchieri."""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.enums import GlassType, Glassware, ServingIce
from app.domain.glassware_catalogues import GlasswareCatalogue
from app.domain.serving_geometry import GlassModel, GlassShape, compatible_ices


class GlassModelOut(BaseModel):
    """Un bicchiere di un catalogo: misure della scheda, profilo e ghiacci.

    `profile_mm` sono i diametri interni della coppa, dal fondo alla bocca,
    a quote equispaziate su `depth_mm`: lo studio li disegna in scala senza
    rifare la geometria. `estimated` elenca i rapporti di forma che la
    scheda non dava e sono presi per ipotesi.
    """

    glass: GlassType
    product: str
    capacity_ml: float
    height_mm: float
    diameter_mm: float
    shape: GlassShape
    source: str
    depth_mm: float
    stem_mm: float
    profile_mm: list[float]
    compatible_ice: list[ServingIce]
    estimated: list[str]

    @classmethod
    def from_entity(cls, model: GlassModel) -> GlassModelOut:
        return cls(
            glass=model.glass,
            product=model.product,
            capacity_ml=model.capacity_ml,
            height_mm=model.height_mm,
            diameter_mm=model.diameter_mm,
            shape=model.shape,
            source=model.source,
            depth_mm=model.profile.depth_mm,
            stem_mm=model.stem_mm,
            profile_mm=list(model.profile.diameters_mm),
            compatible_ice=list(compatible_ices(model.profile)),
            estimated=list(model.estimated),
        )


class GlasswareOut(BaseModel):
    """Un catalogo: la linea, chi la produce e i bicchieri che contiene.

    Un tipo assente non c'è: la linea non lo produce. `OTHER` non compare
    mai, perché non ha misure in nessun catalogo.
    """

    glassware: Glassware
    name: str
    maker: str
    description: str
    glasses: list[GlassModelOut]

    @classmethod
    def from_entity(cls, catalogue: GlasswareCatalogue) -> GlasswareOut:
        return cls(
            glassware=catalogue.glassware,
            name=catalogue.name,
            maker=catalogue.maker,
            description=catalogue.description,
            glasses=[GlassModelOut.from_entity(model) for model in catalogue.models.values()],
        )
