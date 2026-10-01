"""bicchiere di servizio: colonna `glass` sulle ricette

Revision ID: 9e3b5d7a1c42
Revises: 7c1e4a9b3f20
Create Date: 2026-10-01 18:00:00.000000

A differenza di `serving_ice`, la colonna è **nullable** e senza default: il
bicchiere è facoltativo nel dominio, e `NULL` significa "non dichiarato",
cioè nessun tetto al volume. Le ricette esistenti restano valide così come
sono; il seed assegna il bicchiere ai classici.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9e3b5d7a1c42"
down_revision: str | Sequence[str] | None = "7c1e4a9b3f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column(
            "glass",
            sa.Enum(
                "COUPE",
                "MARTINI",
                "NICK_AND_NORA",
                "ROCKS",
                "DOUBLE_ROCKS",
                "HIGHBALL",
                "COLLINS",
                "FLUTE",
                "WINE",
                "BALLOON",
                "COPPER_MUG",
                "TIKI",
                "HURRICANE",
                "SHOT",
                "OTHER",
                name="glasstype",
                native_enum=False,
                length=16,
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("recipes", "glass")
