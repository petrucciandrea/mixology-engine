# Mixology Engine

Piattaforma per la creazione e il bilanciamento **scientifico** di cocktail
d'autore. Un solver a ottimizzazione vincolata calcola i volumi che portano
una ricetta ai target richiesti — gradazione, zuccheri, acidità, rapporto
zuccheri/acidi, volume servito — applicando il modello di diluizione
termodinamica di Dave Arnold.

Non è un ricettario: è un motore di calcolo. Dato un Daiquiri 60/30/20 e la
richiesta "portalo a 16% vol in una coppa da 150 ml, dentro la finestra dei
sour", risponde `60 / 25 / 12.5` in 22 iterazioni, e dichiara di quanto ha
mancato ciascun bersaglio.

## Quickstart (Docker-first, Mac Intel x86_64)

```bash
make init      # crea .env da .env.example
make up        # build + avvio: PostgreSQL/pgvector, Redis, backend
make migrate   # crea lo schema (estensione vector inclusa)
make seed      # dispensa di 29 ingredienti + 6 classici, idempotente
make check     # lint + type check + 125 test
```

API su <http://localhost:8000>, Swagger su <http://localhost:8000/docs>,
health check su <http://localhost:8000/health>.

Se la porta 5432 o la 8000 sono già occupate da un altro progetto, cambia
`POSTGRES_HOST_PORT` e `BACKEND_PORT` nel `.env`: la rete interna ai
container non ne risente.

## Il modello

Ogni ingrediente porta quattro grandezze misurabili — densità, gradi Brix,
acidità in % peso/volume, ABV in frazione — da cui si calcolano il profilo
della miscela e, applicando la curva di diluizione della tecnica scelta,
quello del drink effettivamente servito.

La distinzione che conta: **ABV e densità lavorano sui volumi, Brix e
acidità sulle masse**. Confondere i due assi produce risultati plausibili e
sbagliati del 10-20%, cioè la differenza fra un drink equilibrato e uno no.

Formule complete in [`docs/DOMAIN_MODEL_AND_MATH.md`](docs/DOMAIN_MODEL_AND_MATH.md),
tassonomia organolettica in [`docs/FLAVOR_TAXONOMY.md`](docs/FLAVOR_TAXONOMY.md).

## Il solver

Trova `x ∈ ℝⁿ`, i volumi in ml, minimizzando la somma pesata degli errori
**relativi** sui target organolettici post-diluizione, soggetto a bounds
per ingrediente e — quando richiesto — a un vincolo di uguaglianza sul
volume finale. Metodo SLSQP (`scipy.optimize`).

Scelte che vale la pena conoscere prima di leggere il codice:

* il volume finale è un **vincolo**, non un obiettivo pesato: una coppa da
  90 ml ne contiene 90 ([ADR-0006](docs/adr/0006-volume-come-vincolo.md));
* il target sul rapporto zuccheri/acidi è riformulato in forma lineare
  (`Brix − r·Acidità`), liscia anche in acidità nulla, dove il rapporto
  avrebbe una singolarità e i gradienti numerici si azzererebbero;
* l'esito porta sempre **stato di convergenza, iterazioni e residui**: una
  ricetta prodotta da un solver non convergiuto non deve essere
  indistinguibile da una ottimizzata bene;
* multi-start deterministico: stesso input, stesso output;
* i volumi tornano arrotondati al passo del dosatore e **il profilo è
  ricalcolato su quelli**: ciò che l'API dichiara è ciò che si ottiene
  versando.

## Architettura

Clean Architecture, con la regola di dipendenza verificabile e non solo
dichiarata: il dominio non importa Pydantic, SQLAlchemy, FastAPI né SciPy,
e i suoi test girano senza database, senza Redis e senza variabili
d'ambiente.

```text
backend/app/
├── domain/          Entità pure (dataclass frozen), formule, porte
│   ├── entities.py        Ingredient, Recipe, PhysicalProfile
│   ├── flavor.py          Tassonomia a 32 descrittori
│   ├── repositories.py    Porte di persistenza (Protocol)
│   └── services/          Calcolo bilanciamento, modello di diluizione
├── application/     Orchestrazione e calcolo numerico
│   ├── solver/            BalancingSolver (SciPy SLSQP)
│   └── use_cases/         Casi d'uso, asyncio.to_thread sul solver
├── infrastructure/  Adapter: SQLAlchemy async, pgvector, Redis
│   └── db/                Modelli ORM, mapper, repository
└── api/             FastAPI: router, DTO Pydantic, traduzione errori
```

Le decisioni architetturali, con i loro costi, sono registrate in
[`docs/adr/`](docs/adr/).

## API

Tutto sotto `/api/v1`, tranne l'health check, che resta su `/health` perché
è un endpoint operativo e la sua URL non deve cambiare con la versione.

| Metodo | Endpoint | Cosa fa |
|--------|----------|---------|
| `POST` | `/balance` | Profilo di una ricetta **non salvata** |
| `POST` | `/optimize` | Ottimizza una ricetta non salvata |
| `GET` | `/ingredients` | Elenco filtrabile e paginato |
| `POST` | `/ingredients` | Aggiunge un ingrediente |
| `GET` | `/ingredients/flavor-descriptors` | Il vocabolario organolettico |
| `DELETE` | `/ingredients/{id}` | Disattiva (non cancella) |
| `GET/POST/PUT/DELETE` | `/recipes[/{id}]` | CRUD ricette |
| `GET` | `/recipes/{id}/balance` | Profilo di una ricetta salvata |
| `POST` | `/recipes/{id}/optimize` | Ottimizza senza sovrascrivere |

`/balance` e `/optimize` esistono in versione non persistita perché è ciò
che regge l'editor: muovere uno slider non deve lasciare una riga nel
database. Ottimizzare è una proposta; scriverla sulla ricetta è una `PUT`
separata, cioè una decisione di chi la legge.

## Test

125 test, 91% di copertura, divisi per layer perché hanno prerequisiti
diversi:

```bash
make test-unit          # 82 — nessuna dipendenza esterna
make test-integration   # 16 — PostgreSQL, transazione annullata per test
make test-api           # 27 — stack completo, via ASGITransport
```

Fra gli unitari ci sono test **property-based** con Hypothesis, che
verificano su migliaia di ricette generate otto invarianti fisiche: la
conservazione della massa dei soluti e del volume di alcol sotto
diluizione, ABV sempre in [0, 1], l'impossibilità che la diluizione
concentri, l'invarianza del rapporto zuccheri/acidi, l'assenza di NaN. Se
una di esse cade, è il modello a essere sbagliato, non il test.

I valori attesi dei test a esempio sono calcolati a mano dalle formule, non
copiati da un'esecuzione: un test che fotografa l'output conferma solo che
il codice non è cambiato, non che è corretto.

## Stato

Fatto: dominio, solver, casi d'uso, persistenza, API, test, CI.

Da fare: il **matcher organolettico** (pgvector + NetworkX) — lo schema e
la tassonomia sono pronti, l'indice HNSW su distanza coseno è già in
migrazione — e il **frontend** Next.js.

## Comandi

`make help` elenca tutto: migrazioni, seed, lint, type check, shell nei
container, psql, redis-cli.
