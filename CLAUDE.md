# CLAUDE.md — Mixology Engine

Motore di bilanciamento scientifico per cocktail: un solver SciPy calcola i
volumi che portano una ricetta ai target (ABV, Brix, acidità, rapporto
zuccheri/acidi, volume finale) applicando il modello di diluizione di Dave
Arnold; un matcher organolettico separato (pgvector + NetworkX) suggerisce
*quali* ingredienti usare. Monorepo: `backend/` (FastAPI) e `frontend/`
(Next.js).

È un progetto da portare a colloqui tecnici: **rigore su Clean
Architecture, DDD e TDD ha priorità sulla velocità**. Davanti a un
compromesso fra soluzione pragmatica e soluzione architetturalmente pulita,
scegli la seconda e spiega il perché.

## Ambiente: tutto in Docker

Mac Intel x86_64. Ogni comando gira nei container, **mai sull'host**: niente
`pip install`, `uv sync`, `npm install` o `pytest` locali. Usa i target del
`Makefile` o `docker compose exec backend|frontend ...`. Immagini e servizi
dichiarati `linux/amd64`.

```bash
make init && make up && make migrate && make seed   # primo avvio
make test-unit          # dominio + solver + matcher, nessuna dipendenza esterna
make test-integration   # repository, PostgreSQL reale (rollback per test)
make test-api           # HTTP end-to-end via ASGITransport, PostgreSQL + Redis
make check              # backend: ruff check + ruff format --check + mypy strict + pytest --cov
make check-frontend     # eslint + tsc --noEmit + next build
make check-all          # entrambi
make format             # ruff format (applica la formattazione)
make makemigrations m="messaggio"   # Alembic autogenerate
make help               # tutto il resto
```

Test singolo: `docker compose exec backend uv run pytest tests/unit/test_flavor.py::test_nome -x`.
La copertura si attiva solo con `--cov` (`make test`, `make test-cov`, CI) e
la soglia `fail_under = 85` sta in `[tool.coverage.report]` del
`pyproject.toml`: ha senso solo sull'intera suite, quindi i run parziali
girano senza copertura.

Porte: studio `:3000`, API `:8000` (Swagger su `/docs`), health su `/health`
(fuori da `/api/v1` di proposito). Porte host configurabili nel `.env`.

## Architettura backend (`backend/app/`)

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

## Decisioni di dominio da non sfumare

Registrate in `docs/adr/` (immutabili: una decisione che cambia si supera con
un nuovo ADR, non si riscrive). Le più vincolanti:

1. **Il solver non sceglie gli ingredienti** (ADR-0001): calcola solo i
   volumi. La selezione è del matcher. È il cuore del progetto.
2. **Profilo organolettico a 32 descrittori espliciti** in
   `domain/flavor.py` (ADR-0005, `docs/FLAVOR_TAXONOMY.md`), non embedding.
   Non proporre sentence-transformers/torch se l'utente non lo chiede.
3. **Il volume finale è un vincolo di uguaglianza**, non un obiettivo pesato
   (ADR-0006).
4. **Sostituzione ≠ abbinamento** (ADR-0007): sostituti via similarità del
   coseno pgvector × compatibilità fisica; abbinamenti via PageRank
   personalizzato sul grafo di co-occorrenza. `FlavorProfile.cosine_similarity`
   è l'implementazione di riferimento: pgvector deve restituire gli stessi
   numeri.

Fisica (formule in `docs/DOMAIN_MODEL_AND_MATH.md`): **ABV e densità
lavorano sui volumi, Brix e acidità sulle masse** (volume × densità). ABV è
una frazione in [0, 1], Brix in % peso, acidità in % p/v in [0, 10]. Sempre
distinguere pre- e post-diluizione nei nomi. Niente formule approssimate o
mock della fisica: si implementa il modello reale.

Il solver restituisce sempre stato di convergenza, iterazioni e residui; è
deterministico (multi-start a seed fisso); arrotonda i volumi al passo del
dosatore e **ricalcola il profilo sui volumi arrotondati**.

## Lingua

- **Codice in inglese** (ubiquitous language: entità, campi, metodi,
  messaggi delle eccezioni). Non reintrodurre nomi italiani come `nome` o
  `ingredienti`.
- **Commenti, docstring, documentazione, ADR e messaggi di commit in
  italiano.** I commenti spiegano il *perché* di una scelta (algoritmica,
  fisica, architetturale), come nel codice esistente.
- Etichette dell'interfaccia in italiano da bar (es. "Shakerato"), gli
  identificatori TypeScript restano in inglese.

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

## Frontend (`frontend/src/`)

Next.js 15 App Router, React 19, TypeScript strict (`noUncheckedIndexedAccess`),
Tailwind v4, Recharts, primitive Radix in stile shadcn (`components/ui/`).

- `types/api.ts`: contratto HTTP **scritto a mano** (non generato), con nomi e
  commenti di dominio. Un cambio di DTO sul backend va riportato qui.
- `lib/api.ts`: unico punto che conosce la rete; gli errori diventano
  `ApiError` con `type` e `message` dal formato `{error: {type, message}}`.
- `hooks/useRecipe.ts`: stato della ricetta, debounce degli slider, scarto
  delle risposte fuori ordine.
- `components/studio/`: canvas, radar, pannelli solver e matcher.
- Il browser raggiunge il backend via `NEXT_PUBLIC_API_URL` (porta
  pubblicata), non l'hostname `backend`.

Prossimo pezzo aperto: vista a rete del grafo dei sapori (D3) sopra
`/match/graph` e `/match/bridge`, già pronti.

## Git e CI

- Branch principale `main`: la CI si attiva sui push a `main` e sulle PR.
- Commit convenzionali con soggetto in italiano:
  `feat(matching): ...`, `fix(infra): ...`, `refactor(domain): ...`,
  `test: ...`, `chore: ...`, `build: ...`.
- La CI (`.github/workflows/`) esegue ruff check + ruff format --check +
  mypy + migrazioni + pytest + downgrade sul backend, eslint + tsc + build
  sul frontend. Prima di dichiarare un lavoro finito: `make check-all`.
- `uv.lock` e `package-lock.json` sono vincolanti (`--frozen`, `npm ci`):
  nuove dipendenze si aggiungono dal container e si committa il lock.
