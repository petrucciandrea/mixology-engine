# CLAUDE.md — Backend (`backend/app/`)

Regole valide solo per il backend. Ambiente Docker, decisioni di dominio,
lingua e git/CI sono nel `CLAUDE.md` della radice.

## Architettura (`app/`)

Regola di dipendenza verso l'interno, verificabile:

| Layer | Contiene | Può importare |
|---|---|---|
| `domain/` | Entità `@dataclass(frozen=True, slots=True)`, formule, tassonomia sapori, porte (`Protocol`), errori | solo stdlib |
| `application/` | `solver/` (SciPy SLSQP), `matching/` (NetworkX), `use_cases/` | domain, SciPy, NetworkX |
| `infrastructure/` | ORM SQLAlchemy async, mapper, repository, ricerca pgvector, cache Redis | domain |
| `api/` | Router FastAPI, DTO Pydantic in `schemas/`, traduzione errori | tutto |
| `api/deps.py` | **Composition root**: unico punto dove si sceglie l'adapter per ogni porta | tutto |

Vincoli da rispettare:

- **`domain/` non importa Pydantic, SQLAlchemy, FastAPI, SciPy, NumPy né
  NetworkX.** Validazione negli `__post_init__` (un'entità che esiste è
  valida); errori come sottoclassi di `DomainError` in `domain/errors.py`.
- **DTO Pydantic solo in `api/schemas/`**, con conversione esplicita
  (`from_entity` / `to_domain`). I range numerici dei DTO si leggono dalle
  costanti del dominio (es. `MAX_BRIX`), non si riscrivono.
- **Porte come `Protocol`** in `domain/repositories.py` e
  `domain/matching.py`; gli adapter in `infrastructure/` non ereditano. La
  conformità la verifica MyPy tramite le annotazioni di ritorno in
  `api/deps.py`: una nuova porta si registra lì.
- **Nessun `HTTPException` nei casi d'uso.** Si solleva un errore di dominio;
  lo status code si decide solo in `api/errors.py` (`_STATUS_BY_ERROR`).
- **Transazioni tramite `UnitOfWork`** nel caso d'uso, non nel router.
- **Lavoro CPU-bound (solver, grafo) con `asyncio.to_thread`**; il calcolo
  del solo profilo resta nella coroutine (ADR-0002).
- **Una sola `Base` ORM** in `infrastructure/db/base.py`, da importare come
  `from app.infrastructure.db import Base` (ADR-0003). Alembic usa
  `asyncpg` e legge l'URL da `Settings`; l'estensione `vector` va creata a
  mano nella migrazione. Le migrazioni devono avere un `downgrade`
  funzionante: la CI esegue `alembic downgrade base`.
- **Configurazione solo da `app/core/config.py`** (`get_settings()`); nessun
  `os.environ` altrove.
- MyPy `strict`: ogni funzione è tipizzata. SciPy/pgvector/NetworkX non hanno
  stub e vanno incapsulati dietro firme tipizzate del progetto.

## Fisica e solver

Fisica (formule in `../docs/DOMAIN_MODEL_AND_MATH.md`): **ABV e acidità
lavorano sui volumi, il Brix sulle masse** (volume × densità). ABV è una
frazione in [0, 1], Brix in % peso di *zucchero* (non la lettura del
rifrattometro), acidità in % p/v in [0, 10], senza densità. Il rapporto
zuccheri/acidi è un quoziente di masse, assente sotto 0.5 % p/v di acidità, e
il giudizio dolce/aspro vale solo per i sour (ADR-0011). Sempre distinguere
pre- e post-diluizione nei nomi. Niente formule approssimate o mock della
fisica: si implementa il modello reale.

Il solver restituisce sempre stato di convergenza, iterazioni e residui; è
deterministico (multi-start a seed fisso); arrotonda i volumi al passo del
dosatore e **ricalcola il profilo sui volumi arrotondati**.

## Test (TDD)

- Test per layer, ognuno con il suo `conftest.py`. `tests/conftest.py` resta
  minimo e **non deve importare l'app**: i test unitari girano senza
  database, Redis né variabili d'ambiente.
- I valori attesi dei test a esempio si **calcolano a mano dalle formule**,
  non si copiano da un'esecuzione. Le fixture usano ingredienti con valori
  fisici realistici (`tests/unit/conftest.py`).
- Invarianti fisiche con **Hypothesis** (`test_balance_properties.py`):
  conservazione di soluti e alcol, ABV in [0, 1], nessun NaN, ecc. Una nuova
  formula merita una proprietà, non solo esempi.
- Integrazione: transazione annullata per test (`create_savepoint`), engine
  con `NullPool` per test. API: app reale via `ASGITransport`, sostituita
  solo la sessione tramite `dependency_overrides`; Redis dei test sul db 15.
- Marker `integration` e `api` dichiarati con `--strict-markers`.
