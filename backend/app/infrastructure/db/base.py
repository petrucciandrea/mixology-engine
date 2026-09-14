"""Base dichiarativa SQLAlchemy 2.0.

Tutti i modelli ORM di infrastructure/ ereditano da questa Base.
`target_metadata` in Alembic punta a `Base.metadata`: ogni nuovo modello
importato qui (o in un __init__ che lo re-importa) viene rilevato
automaticamente dalle migrazioni `--autogenerate`.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# NOTE: quando aggiungeremo i modelli ORM (es. IngredientModel, RecipeModel)
# andranno importati qui sotto affinché Alembic li veda in autogenerate:
# from app.infrastructure.db.models.ingredient import IngredientModel  # noqa: F401
