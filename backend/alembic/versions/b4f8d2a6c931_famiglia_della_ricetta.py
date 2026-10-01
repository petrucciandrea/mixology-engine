"""famiglia della ricetta: colonna `family` sulle ricette

Revision ID: b4f8d2a6c931
Revises: 9e3b5d7a1c42
Create Date: 2026-10-01 20:00:00.000000

Come `glass`, la colonna è **nullable** e senza default: la famiglia è
facoltativa nel dominio e `NULL` significa "non classificata". Le ricette
esistenti restano valide; il seed assegna la famiglia ai classici.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4f8d2a6c931"
down_revision: str | Sequence[str] | None = "9e3b5d7a1c42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column(
            "family",
            sa.Enum(
                "SOUR",
                "SPIRIT_FORWARD",
                "HIGHBALL",
                "TROPICAL",
                "SPRITZ",
                "SPARKLING",
                "EMULSIFIED",
                name="recipefamily",
                native_enum=False,
                length=16,
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("recipes", "family")
