"""Fixture globali.

Volutamente minimo: questo file viene importato da **tutta** la suite,
compresi i test di dominio. Importare qui l'applicazione FastAPI —
com'era prima — significava che anche i test puri di dominio
richiedevano `DATABASE_URL` e `REDIS_URL`, perche' l'import creava engine
e connection pool. I test piu' veloci e indipendenti del progetto erano i
piu' accoppiati all'infrastruttura.

Ora ogni layer ha il proprio conftest:
  * `tests/unit/`        — nessuna dipendenza esterna, gira ovunque;
  * `tests/integration/` — richiede PostgreSQL;
  * `tests/api/`         — richiede l'intero stack.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
