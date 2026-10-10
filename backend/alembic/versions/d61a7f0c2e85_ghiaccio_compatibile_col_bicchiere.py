"""ghiaccio compatibile col bicchiere: colonna di ghiaccio e riallineamento

Revision ID: d61a7f0c2e85
Revises: b4f8d2a6c931
Create Date: 2026-10-10 12:00:00.000000

Nessuna modifica allo schema: `serving_ice` è un `VARCHAR(16)` senza vincolo
di valori (`native_enum=False`), quindi il nuovo valore `SPEAR` ci sta già.

È una migrazione **di dati**. Da ADR-0012 l'aggregate `Recipe` rifiuta un
ghiaccio che non entra nel bicchiere, e una riga salvata prima con una
coppia ora impossibile non si potrebbe più caricare. Le coppie sono quelle
che la regola geometrica di `serving_geometry` esclude oggi, **scritte qui
per esteso** e non importate dal dominio: una migrazione è una fotografia,
e non deve cambiare comportamento se domani la regola si affina. Prima di
questa revisione la colonna di ghiaccio non esisteva, quindi le coppie da
correggere riguardano solo cubo grosso e cubetti. Il ripiego è lo stesso
dell'editor: cubetti se entrano, altrimenti senza ghiaccio.

Il downgrade riporta le colonne a cubetti, l'unico valore noto alla
revisione precedente che entra in ogni bicchiere che accoglie una colonna;
il riallineamento dell'upgrade non si annulla, perché le coppie originali
non erano valide.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d61a7f0c2e85"
down_revision: str | Sequence[str] | None = "b4f8d2a6c931"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Bicchieri in cui il cubo grosso non entra (sporge o non passa dalla bocca).
_NO_LARGE_CUBE = (
    "COUPE",
    "MARTINI",
    "NICK_AND_NORA",
    "HIGHBALL",
    "COLLINS",
    "FLUTE",
    "WINE",
    "HURRICANE",
)


def upgrade() -> None:
    recipes = sa.table("recipes", sa.column("glass"), sa.column("serving_ice"))
    op.execute(
        recipes.update()
        .where(recipes.c.glass.in_(_NO_LARGE_CUBE), recipes.c.serving_ice == "LARGE_CUBE")
        .values(serving_ice="CUBES")
    )
    # Nel bicchierino non entrano né il cubo grosso né i cubetti.
    op.execute(
        recipes.update()
        .where(recipes.c.glass == "SHOT", recipes.c.serving_ice.in_(("LARGE_CUBE", "CUBES")))
        .values(serving_ice="NONE")
    )


def downgrade() -> None:
    recipes = sa.table("recipes", sa.column("serving_ice"))
    op.execute(recipes.update().where(recipes.c.serving_ice == "SPEAR").values(serving_ice="CUBES"))
