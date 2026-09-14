"""Base dichiarativa SQLAlchemy 2.0 — unica per tutto il progetto.

Esisteva una seconda `Base` in `session.py`: i modelli ORM ereditavano da
quella, mentre Alembic ispezionava questa. Il risultato era che
`alembic revision --autogenerate` produceva migrazioni vuote senza
segnalare nulla, perché i metadata che leggeva non contenevano tabelle.

Da qui la regola: **una sola `Base`, definita qui**. Il modo corretto di
raggiungerla è `from app.infrastructure.db import Base`, che importando il
package registra anche tutti i modelli su `Base.metadata` (vedi
`__init__.py`) e rende l'autogenerate affidabile per costruzione.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
