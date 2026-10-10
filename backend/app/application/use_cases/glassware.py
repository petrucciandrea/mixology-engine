"""Caso d'uso sul catalogo dei bicchieri."""

from __future__ import annotations

from app.domain.services.glassware import GlassSpec, glass_catalogue


class ListGlasswareUseCase:
    """Bicchieri con capienza e ghiacci compatibili.

    Non tocca il database: il catalogo è vocabolario di dominio. Passa
    comunque da un caso d'uso perché il router non conosca il dominio per
    altre vie che questa, come per tutti gli altri endpoint.
    """

    def execute(self) -> tuple[GlassSpec, ...]:
        return glass_catalogue()
