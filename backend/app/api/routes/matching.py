"""Endpoint del matcher organolettico.

Sono deliberatamente separati da quelli di bilanciamento: il solver
risponde a "quanto", il matcher a "cosa" (ADR-0001). Tenere le due cose su
router distinti rende la separazione visibile anche in OpenAPI, dove il
raggruppamento per tag è la prima cosa che si legge.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_describe_graph_use_case,
    get_find_bridge_use_case,
    get_find_substitutes_use_case,
    get_suggest_pairings_use_case,
)
from app.api.schemas.matching import (
    FlavorBridgeOut,
    GraphOverviewOut,
    PairingRequest,
    PairingSuggestionOut,
    SubstitutionOut,
)
from app.application.use_cases.matching import (
    DescribeFlavorGraphUseCase,
    FindFlavorBridgeUseCase,
    FindSubstitutesUseCase,
    SuggestPairingsUseCase,
)

router = APIRouter(prefix="/match", tags=["matching"])


@router.get(
    "/substitutes/{ingredient_id}",
    response_model=list[SubstitutionOut],
    summary="Con cosa posso sostituire questo ingrediente",
)
async def find_substitutes(
    ingredient_id: str,
    use_case: Annotated[FindSubstitutesUseCase, Depends(get_find_substitutes_use_case)],
    # Tetto piu' alto degli altri elenchi: il riordino a due assi puo'
    # retrocedere candidati organoletticamente ottimi, e chi compone una
    # ricetta ha ragione di volerli vedere comunque, con le loro avvertenze.
    # Resta una singola query indicizzata.
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
    same_category_only: bool = False,
) -> list[SubstitutionOut]:
    candidates = await use_case.execute(
        ingredient_id, limit=limit, same_category_only=same_category_only
    )
    return [SubstitutionOut.from_entity(candidate) for candidate in candidates]


@router.post(
    "/pairings",
    response_model=list[PairingSuggestionOut],
    summary="Cosa aggiungere a una ricetta in costruzione",
)
async def suggest_pairings(
    payload: PairingRequest,
    use_case: Annotated[SuggestPairingsUseCase, Depends(get_suggest_pairings_use_case)],
) -> list[PairingSuggestionOut]:
    suggestions = await use_case.execute(payload.ingredient_ids, limit=payload.limit)
    return [PairingSuggestionOut.from_entity(item) for item in suggestions]


@router.get(
    "/bridge",
    response_model=FlavorBridgeOut,
    summary="Gli ingredienti che collegano due estremi lontani",
)
async def find_bridge(
    source_id: Annotated[str, Query(description="Ingrediente di partenza")],
    target_id: Annotated[str, Query(description="Ingrediente di arrivo")],
    use_case: Annotated[FindFlavorBridgeUseCase, Depends(get_find_bridge_use_case)],
) -> FlavorBridgeOut:
    bridge = await use_case.execute(source_id, target_id)
    if bridge is None:
        # I due ingredienti esistono (il caso d'uso lo ha verificato) ma non
        # sono connessi nel grafo: 404 sarebbe fuorviante, perché a mancare
        # non è una risorsa ma una relazione fra due risorse esistenti.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "nessun percorso di affinità fra i due ingredienti: "
                "servono ricette o profili che li colleghino"
            ),
        )
    return FlavorBridgeOut.from_entity(bridge)


@router.get(
    "/graph",
    response_model=GraphOverviewOut,
    summary="Struttura del grafo e famiglie di ingredienti",
)
async def describe_graph(
    use_case: Annotated[DescribeFlavorGraphUseCase, Depends(get_describe_graph_use_case)],
) -> GraphOverviewOut:
    return GraphOverviewOut.from_entity(await use_case.execute())
