"""Caso d'uso sui cataloghi di bicchieri."""

from __future__ import annotations

from app.domain.glassware_catalogues import CATALOGUES, GlasswareCatalogue


class ListGlasswareUseCase:
    """I cataloghi di bicchieri, nell'ordine dell'enum `Glassware`.

    Non tocca il database: i cataloghi sono vocabolario di dominio. Passa
    comunque da un caso d'uso perché il router non conosca il dominio per
    altre vie che questa, come per tutti gli altri endpoint.
    """

    def execute(self) -> tuple[GlasswareCatalogue, ...]:
        return tuple(CATALOGUES.values())
