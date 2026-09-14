"""Package di persistenza.

Importare questo package registra ogni modello ORM su `Base.metadata`.
È il punto unico da cui Alembic e i test devono prendere i metadata: così
aggiungere un modello non richiede di ricordarsi di importarlo altrove
perché le migrazioni lo vedano.
"""

from __future__ import annotations

from . import models as _models  # noqa: F401  (import per side-effect: registra le tabelle)
from .base import Base

__all__ = ["Base"]
