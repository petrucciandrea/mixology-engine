"""catalogo dei bicchieri: colonna `glassware` sulle ricette

Revision ID: e4b2c9d71f36
Revises: d61a7f0c2e85
Create Date: 2026-10-10 18:00:00.000000

La ricetta ricorda da quale catalogo viene il suo bicchiere (ADR-0013). La
colonna è NOT NULL: le righe esistenti ricevono `GENERIC`, che è proprio
ciò che erano (misure tipiche, non di un prodotto), e il default di
migrazione si toglie subito dopo. Nel dominio il default resta `GENERIC`,
ma lo applica il codice: lo schema non deve inventare valori.

Le misure del catalogo generico cambiano con questa revisione (ora
ricavate da forma e capienza), e rispetto alla regola precedente due coppie
non entrano più: la colonna nell'highball (coppa da ~105 mm, la colonna ne
misura 120) e il cubo grosso nel tiki (bocca troppo stretta). Come nella
revisione precedente le coppie sono scritte per esteso, e il ripiego è lo
stesso dell'editor: cubetti.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4b2c9d71f36"
down_revision: str | Sequence[str] | None = "d61a7f0c2e85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: (bicchiere, ghiaccio) generici che con le nuove misure non entrano più.
_NO_LONGER_FIT = (("HIGHBALL", "SPEAR"), ("TIKI", "LARGE_CUBE"))


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column(
            "glassware",
            sa.Enum(
                "GENERIC",
                "LUIGI_BORMIOLI",
                "SCHOTT_ZWIESEL",
                "NUDE",
                name="glassware",
                native_enum=False,
                length=24,
            ),
            server_default="GENERIC",
            nullable=False,
        ),
    )
    op.alter_column("recipes", "glassware", server_default=None)

    recipes = sa.table("recipes", sa.column("glass"), sa.column("serving_ice"))
    for glass, ice in _NO_LONGER_FIT:
        op.execute(
            recipes.update()
            .where(recipes.c.glass == glass, recipes.c.serving_ice == ice)
            .values(serving_ice="CUBES")
        )


def downgrade() -> None:
    op.drop_column("recipes", "glassware")
