"""Confine transazionale su una sessione SQLAlchemy."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyUnitOfWork:
    """Implementa la porta `UnitOfWork` delegando alla sessione.

    Non eredita dal `Protocol` di dominio: la conformità è strutturale e
    verificata da MyPy nel punto di composizione. È questo che tiene la
    dipendenza rivolta verso l'interno — l'infrastruttura conosce il
    dominio, il dominio non conosce l'infrastruttura.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
