"""Engine e session factory asincroni, creati pigramente.

Prima l'engine e la session factory venivano istanziati all'import del
modulo. La conseguenza pratica era che importare *qualunque* cosa che
arrivasse fin qui — inclusi, per via del `conftest`, i test puri di
dominio — richiedeva un `DATABASE_URL` valido. I test più veloci e più
indipendenti del progetto erano i più accoppiati all'infrastruttura.

Qui l'engine nasce alla prima richiesta e vive in cache per il resto del
processo: il pool di connessioni resta unico, ma nessuno lo paga solo per
aver importato il modulo.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Engine condiviso dal processo.

    `pool_pre_ping` verifica la connessione prima di usarla: senza, dopo
    un riavvio del container Postgres l'applicazione continuerebbe a
    pescare dal pool connessioni ormai morte.
    """
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        echo=settings.echo_sql,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        # Gli oggetti restano leggibili dopo il commit: senza questo, ogni
        # attributo letto dopo un commit scatenerebbe un refresh implicito
        # — che in un contesto async significa I/O in un punto in cui il
        # chiamante non lo si aspetta.
        expire_on_commit=False,
    )


async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Una sessione per unità di lavoro, con rollback garantito.

    Il commit è responsabilità del caso d'uso (che sa quando l'operazione
    di business è conclusa); qui si garantisce solo che nulla resti
    committato a metà se qualcosa solleva.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Chiude il pool. Invocato allo spegnimento dell'applicazione."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
