"""Modelli ORM.

Sono deliberatamente separati dalle entità di dominio: la loro forma
risponde alle esigenze del database (chiavi, indici, vincoli, tipi di
colonna), non a quelle del dominio. La traduzione fra i due mondi sta in
`mappers.py`.

Il prezzo è un mapping esplicito da mantenere; il ritorno è che lo schema
può evolvere — denormalizzare, aggiungere indici, cambiare il tipo di una
colonna — senza che il dominio se ne accorga, e che il dominio non
contiene un solo import di SQLAlchemy.
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import DilutionMethod, IngredientCategory
from app.domain.flavor import FLAVOR_VECTOR_DIMENSION

from .base import Base


class IngredientModel(Base):
    __tablename__ = "ingredients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[IngredientCategory] = mapped_column(
        # `native_enum=False` mappa l'enum su VARCHAR + CHECK invece che su
        # un tipo ENUM di PostgreSQL: aggiungere un valore diventa una
        # modifica di vincolo, non un `ALTER TYPE` che in PostgreSQL non è
        # reversibile dentro una transazione.
        Enum(IngredientCategory, native_enum=False, length=32),
        nullable=False,
    )

    density_g_ml: Mapped[float] = mapped_column(Float, nullable=False)
    brix: Mapped[float] = mapped_column(Float, nullable=False)
    acidity: Mapped[float] = mapped_column(Float, nullable=False)
    abv: Mapped[float] = mapped_column(Float, nullable=False)

    #: Profilo organolettico a descrittori espliciti (vedi domain/flavor.py).
    #: Nullable: un ingrediente può essere inserito prima di essere profilato,
    #: e resta perfettamente utilizzabile dal solver, che usa solo le
    #: grandezze fisiche. Senza vettore è invisibile al matcher, non al bar.
    flavor_vector: Mapped[list[float] | None] = mapped_column(
        Vector(FLAVOR_VECTOR_DIMENSION), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    recipe_items: Mapped[list[RecipeIngredientModel]] = relationship(back_populates="ingredient")

    __table_args__ = (
        UniqueConstraint("name", name="uq_ingredients_name"),
        # I range fisici sono già garantiti dalle entità di dominio. Ripeterli
        # qui protegge da ciò che non passa dal dominio — una migrazione di
        # dati, un import massivo, una sessione psql — e rende lo schema
        # autoesplicativo per chi legge solo il database.
        CheckConstraint("abv >= 0 AND abv <= 1", name="ck_ingredients_abv_fraction"),
        CheckConstraint("brix >= 0 AND brix <= 100", name="ck_ingredients_brix_range"),
        CheckConstraint("acidity >= 0 AND acidity <= 10", name="ck_ingredients_acidity_range"),
        CheckConstraint(
            "density_g_ml >= 0.7 AND density_g_ml <= 1.6", name="ck_ingredients_density_range"
        ),
        Index("ix_ingredients_category_active", "category", "is_active"),
    )


class RecipeModel(Base):
    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    dilution_method: Mapped[DilutionMethod] = mapped_column(
        Enum(DilutionMethod, native_enum=False, length=16), nullable=False
    )
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    ingredients: Mapped[list[RecipeIngredientModel]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        # `position` conserva l'ordine di scrittura della ricetta, che è
        # informazione reale: è l'ordine di versamento, e il solver assegna
        # i volumi per posizione.
        order_by="RecipeIngredientModel.position",
        lazy="selectin",
    )


class RecipeIngredientModel(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[str] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[str] = mapped_column(
        # RESTRICT e non CASCADE: cancellare un ingrediente non deve
        # svuotare in silenzio le ricette che lo usano. Per togliere un
        # ingrediente dal listino si usa `is_active = False`.
        ForeignKey("ingredients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    volume_ml: Mapped[float] = mapped_column(Float, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    recipe: Mapped[RecipeModel] = relationship(back_populates="ingredients")
    ingredient: Mapped[IngredientModel] = relationship(back_populates="recipe_items", lazy="joined")

    __table_args__ = (
        # Rispecchia l'invariante dell'aggregate `Recipe`: un ingrediente
        # compare una volta sola per ricetta.
        UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredient"),
        CheckConstraint("volume_ml > 0", name="ck_recipe_ingredients_positive_volume"),
        Index("ix_recipe_ingredients_recipe", "recipe_id"),
    )
