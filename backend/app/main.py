"""Entry point applicazione FastAPI.

Nota architetturale: questo modulo fa solo wiring (crea l'app, monta i
router). Non contiene logica di dominio né di infrastruttura — resta
sottile per costruzione (Clean Architecture: il framework è un dettaglio).
"""

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Mixology Engine API",
    description="Motore di bilanciamento cocktail — Clean Architecture / DDD",
    version="0.1.0",
    debug=settings.debug,
)

app.include_router(health_router)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"service": "mixology-engine", "status": "running"}
