"""Health check "reale": verifica la connettività effettiva con DB e Redis,
non solo che il processo FastAPI sia in piedi. Questo è ciò che rende lo
smoke test significativo per validare l'intero stack Docker Compose.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.infrastructure.redis_client import get_redis

router = APIRouter(tags=["health"])

ComponentStatus = Literal["connected", "unreachable"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: ComponentStatus
    redis: ComponentStatus


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> HealthResponse:
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

    overall = "ok" if db_status == "connected" and redis_status == "connected" else "degraded"
    return HealthResponse(status=overall, database=db_status, redis=redis_status)
