"""Errori di dominio.

Il dominio non conosce HTTP: solleva eccezioni che descrivono la
violazione in termini di business. È il layer API a tradurle in status
code (vedi `app/api/errors.py`), così la stessa regola vale identica se
domani il dominio viene invocato da una CLI o da un worker.
"""

from __future__ import annotations


class DomainError(Exception):
    """Radice di tutti gli errori di dominio."""


class InvalidPhysicalProfileError(DomainError):
    """Un parametro fisico è fuori dal range ammesso per un liquido da bar."""


class InvalidFlavorProfileError(DomainError):
    """Il vettore organolettico non rispetta la tassonomia dichiarata."""


class InvalidVolumeError(DomainError):
    """Un volume non è strettamente positivo."""


class InvalidRecipeError(DomainError):
    """La ricetta è strutturalmente invalida (vuota, o con duplicati)."""


class EntityNotFoundError(DomainError):
    """L'entità richiesta non esiste nel repository."""

    def __init__(self, entity: str, entity_id: str) -> None:
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"{entity} '{entity_id}' not found")


class DuplicateEntityError(DomainError):
    """Esiste già un'entità con la stessa chiave naturale."""

    def __init__(self, entity: str, field: str, value: str) -> None:
        self.entity = entity
        self.field = field
        self.value = value
        super().__init__(f"{entity} with {field} '{value}' already exists")


class SolverError(DomainError):
    """Il problema di ottimizzazione è mal posto e non può essere risolto."""
