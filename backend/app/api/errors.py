"""Traduzione degli errori di dominio in risposte HTTP.

Il dominio solleva eccezioni che parlano di regole di business; qui, e
solo qui, diventano status code. Il vantaggio è che un caso d'uso non
contiene un solo `HTTPException`: la stessa logica, invocata da una CLI o
da un worker, solleva gli stessi errori e nessuno deve fingere di essere
una richiesta HTTP.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.errors import (
    DomainError,
    DuplicateEntityError,
    EntityNotFoundError,
    InvalidFlavorProfileError,
    InvalidPhysicalProfileError,
    InvalidRecipeError,
    InvalidServingConditionsError,
    InvalidVolumeError,
    SolverError,
)

#: Mappa esplicita eccezione → status. Preferita a una catena di `isinstance`
#: perché è leggibile a colpo d'occhio e cresce senza ramificazioni.
_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    EntityNotFoundError: status.HTTP_404_NOT_FOUND,
    DuplicateEntityError: status.HTTP_409_CONFLICT,
    InvalidVolumeError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InvalidServingConditionsError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InvalidRecipeError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InvalidPhysicalProfileError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InvalidFlavorProfileError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    SolverError: status.HTTP_422_UNPROCESSABLE_ENTITY,
}

#: Un errore di dominio non previsto resta un errore del *client*: significa
#: che una regola di business è stata violata, non che il server è rotto.
_DEFAULT_STATUS = status.HTTP_400_BAD_REQUEST


def _status_for(error: DomainError) -> int:
    for error_type, http_status in _STATUS_BY_ERROR.items():
        if isinstance(error, error_type):
            return http_status
    return _DEFAULT_STATUS


async def domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Formato di errore unico per tutta l'API.

    `type` è il nome della classe di dominio: dà al client qualcosa di
    stabile su cui ramificare, mentre `message` è pensato per essere letto
    da una persona e può cambiare senza rompere nulla.
    """
    assert isinstance(exc, DomainError)  # noqa: S101  (garantito dalla registrazione)
    return JSONResponse(
        status_code=_status_for(exc),
        content={"error": {"type": type(exc).__name__, "message": str(exc)}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra il gestore sulla radice della gerarchia.

    Registrare `DomainError` copre anche ogni sottoclasse futura: un nuovo
    errore di dominio riceve una risposta sensata (400) senza che nessuno
    debba ricordarsi di aggiungerlo, e lo si affina qui solo quando merita
    uno status più preciso.
    """
    app.add_exception_handler(DomainError, domain_error_handler)
