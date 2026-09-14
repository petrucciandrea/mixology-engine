from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.models import DilutionMethod
from app.infrastructure.db.session import Base


FLAVOR_VECTOR_DIMENSION = 38


class IngredientEntity(Base):
    __tablename__ = "ingredients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    categoria: Mapped[str] = mapped_column(String(100), index=True)
    density_g_ml: Mapped[float] = mapped_column(Float, nullable=False)
    brix: Mapped[float] = mapped_column(Float, nullable=False)
    acidity: Mapped[float] = mapped_column(Float, nullable=False)
    abv: Mapped[float] = mapped_column(Float, nullable=False)
    flavor_vector: Mapped[list[float] | None] = mapped_column(
        Vector(FLAVOR_VECTOR_DIMENSION),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    recipe_items: Mapped[list[RecipeIngredientEntity]] = relationship(
        back_populates="ingrediente",
    )


class RecipeEntity(Base):
    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), index=True)
    dilution_method: Mapped[DilutionMethod] = mapped_column(
        Enum(DilutionMethod, native_enum=False),
        nullable=False,
    )
    istruzioni: Mapped[str | None] = mapped_column(Text, nullable=True)

    ingredienti: Mapped[list[RecipeIngredientEntity]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
    )


class RecipeIngredientEntity(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[str] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_id: Mapped[str] = mapped_column(
        ForeignKey("ingredients.id"),
        nullable=False,
    )
    volume_ml: Mapped[float] = mapped_column(Float, nullable=False)

    recipe: Mapped[RecipeEntity] = relationship(back_populates="ingredienti")
    ingrediente: Mapped[IngredientEntity] = relationship(back_populates="recipe_items")
