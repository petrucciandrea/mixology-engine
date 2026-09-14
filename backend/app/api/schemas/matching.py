"""DTO del matcher organolettico."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.application.matching.flavor_graph import GraphStats
from app.application.use_cases.matching import GraphOverview
from app.domain.matching import FlavorBridge, PairingSuggestion, SubstitutionCandidate

from .ingredients import IngredientOut


class SubstitutionOut(BaseModel):
    """Un sostituto proposto, con il ragionamento in chiaro.

    I due assi restano separati invece di essere fusi in `overall`: chi
    legge deve poter capire *perché* un candidato è debole, perché la
    risposta cambia cosa fare. Organoletticamente lontano ma fisicamente
    identico si usa cambiando il carattere del drink; il contrario richiede
    di ridosare, e conviene passare dall'ottimizzatore.
    """

    ingredient: IngredientOut
    flavor_similarity: float = Field(description="Similarità del coseno sul profilo, 0-1")
    physical_compatibility: float = Field(
        description="Quanto si comporta allo stesso modo nel bilanciamento, 0-1"
    )
    overall: float = Field(description="Prodotto dei due assi")
    warnings: list[str] = Field(
        default_factory=list,
        description="Cosa cambia nel drink usando questo sostituto",
    )

    @classmethod
    def from_entity(cls, candidate: SubstitutionCandidate) -> SubstitutionOut:
        return cls(
            ingredient=IngredientOut.from_entity(candidate.ingredient),
            flavor_similarity=candidate.score.flavor_similarity,
            physical_compatibility=candidate.score.physical_compatibility,
            overall=candidate.overall,
            warnings=list(candidate.score.warnings),
        )


class PairingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_ids: Annotated[list[str], Field(min_length=1, max_length=20)]
    limit: Annotated[int, Field(ge=1, le=20)] = 5


class PairingSuggestionOut(BaseModel):
    ingredient: IngredientOut
    affinity: float = Field(description="Punteggio del PageRank personalizzato sui semi indicati")
    rationale: str = Field(description="Da dove viene l'affinità, in chiaro")

    @classmethod
    def from_entity(cls, suggestion: PairingSuggestion) -> PairingSuggestionOut:
        return cls(
            ingredient=IngredientOut.from_entity(suggestion.ingredient),
            affinity=suggestion.affinity,
            rationale=suggestion.rationale,
        )


class FlavorBridgeOut(BaseModel):
    """Il percorso di massima affinità fra due ingredienti lontani."""

    path: list[IngredientOut]
    strength: float = Field(description="Prodotto delle affinità lungo il percorso")
    steps: int = Field(description="Quanti archi separano i due estremi")

    @classmethod
    def from_entity(cls, bridge: FlavorBridge) -> FlavorBridgeOut:
        return cls(
            path=[IngredientOut.from_entity(item) for item in bridge.path],
            strength=bridge.strength,
            steps=max(0, len(bridge.path) - 1),
        )


class GraphStatsOut(BaseModel):
    nodes: int
    edges: int
    density: float
    communities: int

    @classmethod
    def from_entity(cls, stats: GraphStats) -> GraphStatsOut:
        return cls(
            nodes=stats.nodes,
            edges=stats.edges,
            density=stats.density,
            communities=stats.communities,
        )


class FlavorCommunityOut(BaseModel):
    """Una famiglia di ingredienti emersa dai dati, non imposta a priori."""

    size: int
    ingredients: list[IngredientOut]


class GraphOverviewOut(BaseModel):
    stats: GraphStatsOut
    communities: list[FlavorCommunityOut]

    @classmethod
    def from_entity(cls, overview: GraphOverview) -> GraphOverviewOut:
        return cls(
            stats=GraphStatsOut.from_entity(overview.stats),
            communities=[
                FlavorCommunityOut(
                    size=len(group),
                    ingredients=[IngredientOut.from_entity(item) for item in group],
                )
                for group in overview.communities
            ],
        )
