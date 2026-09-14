"""Health check "reale": verifica la connettività effettiva con DB e Redis,
non solo che il processo FastAPI sia in piedi. È ciò che rende lo smoke
test significativo per validare l'intero stack Docker Compose.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import RedisDep, SessionDep

router = APIRouter(tags=["health"])

ComponentStatus = Literal["connected", "unreachable"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: ComponentStatus
    redis: ComponentStatus


@router.get("/health", response_model=HealthResponse)
async def health_check(db: SessionDep, redis: RedisDep, response: Response) -> HealthResponse:
    db_status: ComponentStatus = "connected"
    redis_status: ComponentStatus = "connected"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unreachable"

    try:
        await redis.ping()
    except Exception:
        redis_status = "unreachable"

    healthy = db_status == "connected" and redis_status == "connected"
    if not healthy:
        # 503 e non 200: un orchestratore decide se togliere l'istanza dal
        # bilanciatore leggendo lo status code, non il corpo della risposta.
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if healthy else "degraded",
        database=db_status,
        redis=redis_status,
    )
