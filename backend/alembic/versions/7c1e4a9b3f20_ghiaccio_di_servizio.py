"""ghiaccio di servizio: colonna `serving_ice` sulle ricette

Revision ID: 7c1e4a9b3f20
Revises: 2d335d05d18c
Create Date: 2026-10-01 16:00:00.000000

La colonna è NOT NULL, quindi le righe esistenti hanno bisogno di un valore
al momento dell'ALTER: si usa `NONE` come default **solo di migrazione** e
lo si toglie subito dopo. Il default non deve restare nello schema: nel
dominio il servizio è un dato obbligatorio, e un default nel database
farebbe passare per "senza ghiaccio" una ricetta che non ha detto nulla.
Il valore corretto delle ricette già presenti lo ripristina il seed, che
riallinea i classici per nome.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c1e4a9b3f20"
down_revision: str | Sequence[str] | None = "2d335d05d18c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column(
            "serving_ice",
            sa.Enum(
                "NONE",
                "CUBES",
                "LARGE_CUBE",
                "CRUSHED",
                name="servingice",
                native_enum=False,
                length=16,
            ),
            server_default="NONE",
            nullable=False,
        ),
    )
    op.alter_column("recipes", "serving_ice", server_default=None)


def downgrade() -> None:
    op.drop_column("recipes", "serving_ice")
