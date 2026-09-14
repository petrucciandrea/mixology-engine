"""Entry point applicazione FastAPI.

Nota architetturale: questo modulo fa solo wiring — crea l'app, monta i
router, registra i gestori di errore. Non contiene logica di dominio né
di infrastruttura, e resta sottile per costruzione: in Clean Architecture
il framework web è un dettaglio sostituibile, non il centro del sistema.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.routes.balancing import router as balancing_router
from app.api.routes.health import router as health_router
from app.api.routes.ingredients import router as ingredients_router
from app.api.routes.recipes import router as recipes_router
from app.core.config import get_settings
from app.infrastructure.db.session import dispose_engine
from app.infrastructure.redis_client import dispose_pool


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Chiude i pool allo spegnimento.

    Senza, un reload in sviluppo lascia connessioni appese a Postgres, che
    dopo qualche decina di riavvii esaurisce `max_connections`.
    """
    yield
    await dispose_engine()
    await dispose_pool()


def create_app() -> FastAPI:
    """Factory dell'applicazione.

    Una factory e non un modulo con una variabile globale: i test possono
    costruire istanze indipendenti con configurazioni diverse, senza
    dipendere dall'ordine di import.
    """
    settings = get_settings()

    app = FastAPI(
        title=f"{settings.project_name} API",
        description=(
            "Motore di bilanciamento scientifico per cocktail d'autore. "
            "Il solver calcola i volumi ottimali dati dei target "
            "(ABV, Brix, acidità, rapporto zuccheri/acidi); la selezione "
            "degli ingredienti è demandata al matcher organolettico."
        ),
        version="0.2.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # Health check fuori dal prefisso versionato: è un endpoint
    # operativo, consumato da Docker e dagli orchestratori, e la sua
    # URL non deve cambiare quando l'API passa a /api/v2.
    app.include_router(health_router)

    app.include_router(ingredients_router, prefix=settings.api_v1_prefix)
    app.include_router(recipes_router, prefix=settings.api_v1_prefix)
    app.include_router(balancing_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {
            "service": "mixology-engine",
            "status": "running",
            "version": app.version,
            "docs": "/docs",
        }

    return app


app = create_app()
