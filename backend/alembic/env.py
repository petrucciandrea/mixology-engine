"""Alembic env.py — versione asincrona (SQLAlchemy 2.0 + asyncpg).

Il pattern standard di Alembic è sincrono; qui usiamo
`connection.run_sync(...)` per far girare `context.configure`/
`context.run_migrations` dentro un engine AsyncEngine, che è l'unico
tipo di engine usato dall'app (coerenza con app/infrastructure/db/session.py).
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Import esplicito: registra tutti i modelli ORM su Base.metadata
# prima che Alembic li ispezioni per l'autogenerate.
from app.core.config import get_settings
from app.infrastructure.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# URL letto dalla stessa fonte di verità usata dall'app runtime
# (nessuna duplicazione di credenziali nell'ini).
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Modalità 'offline': genera SQL senza connettersi al DB."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Modalità 'online' asincrona: crea un AsyncEngine e delega
    l'esecuzione sincrona di Alembic dentro `run_sync`.
    """
    connectable: AsyncEngine = create_async_engine(
        config.get_main_option("sqlalchemy.url"),  # type: ignore[arg-type]
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
