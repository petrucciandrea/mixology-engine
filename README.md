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
make check     # lint + type check + 194 test
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

## Il matcher

L'altra metà del sistema, e deliberatamente separata dal solver: il solver
risponde a *quanto*, il matcher a *cosa* ([ADR-0001](docs/adr/0001-solver-separato-dal-matcher.md)).

Due domande che sembrano la stessa e non lo sono, quindi due meccanismi
distinti ([ADR-0007](docs/adr/0007-matcher-similarita-e-affinita.md)):

**Sostituzione.** pgvector cerca per prossimità del coseno sull'indice
HNSW, poi il dominio riordina i candidati moltiplicando la similarità
organolettica per la compatibilità fisica. Uno sciroppo al lime sa
esattamente di lime e ha acidità 0.5 contro 6.0: il prodotto lo retrocede
dove merita, con scritto il perché.

```
Sostituti del succo di lime
  Succo di Limone        aroma 0.98   fisico 0.59   totale 0.58
  Soluzione Citrica 6%   aroma 0.72   fisico 0.57   totale 0.41
  Succo di Pompelmo      aroma 0.89   fisico 0.20   totale 0.18
    ! toglie 4.0% di acidità: reintegrare con succo o soluzione acida
```

**Abbinamento.** Un grafo NetworkX in cui gli archi pesano co-occorrenza
nelle ricette e aromi condivisi. Il PageRank personalizzato sui semi
premia il candidato affine a *tutti* gli ingredienti già nel bicchiere, e
un filtro di ridondanza impedisce il fallimento classico — suggerire il
limone a chi ha già il lime.

```
Abbinamenti per Gin + Vermouth Rosso
  Succo di Lime       0.0722  — compare insieme a Gin in ricette esistenti (citrus, herbaceous)
  Bitter Rosso        0.0634  — compare insieme a Vermouth Rosso in ricette esistenti
  Chartreuse Verde    0.0512  — compare insieme a Gin in ricette esistenti (herbaceous)
```

**Ponti aromatici.** Il cammino di massima affinità fra due estremi
lontani, calcolato su `-log(peso)` così che il percorso più corto sia
quello che massimizza il prodotto delle affinità.

```
Mezcal → Tequila Blanco → Triple Sec → Orgeat     forza 0.039 in 3 passi
```

Il grafo è messo in cache su Redis con chiave l'impronta dei suoi ingressi:
l'invalidazione è automatica, e una cache irraggiungibile degrada la
latenza, mai la disponibilità.

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
│   ├── matching/          Grafo delle affinità (NetworkX)
│   └── use_cases/         Casi d'uso, asyncio.to_thread sul lavoro CPU-bound
├── infrastructure/  Adapter: SQLAlchemy async, pgvector, Redis
│   ├── db/                Modelli ORM, mapper, repository, ricerca vettoriale
│   └── cache/             Cache Redis del grafo
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
| `GET` | `/match/substitutes/{id}` | Con cosa posso sostituirlo |
| `POST` | `/match/pairings` | Cosa aggiungere a una ricetta in costruzione |
| `GET` | `/match/bridge` | Gli ingredienti che collegano due estremi |
| `GET` | `/match/graph` | Struttura del grafo e famiglie di ingredienti |

`/balance` e `/optimize` esistono in versione non persistita perché è ciò
che regge l'editor: muovere uno slider non deve lasciare una riga nel
database. Ottimizzare è una proposta; scriverla sulla ricetta è una `PUT`
separata, cioè una decisione di chi la legge.

## Test

194 test, 92% di copertura, divisi per layer perché hanno prerequisiti
diversi:

```bash
make test-unit          # 124 — nessuna dipendenza esterna
make test-integration   #  28 — PostgreSQL, transazione annullata per test
make test-api           #  42 — stack completo, via ASGITransport
```

Fra gli unitari ci sono test **property-based** con Hypothesis, che
verificano su migliaia di ricette generate otto invarianti fisiche: la
conservazione della massa dei soluti e del volume di alcol sotto
diluizione, ABV sempre in [0, 1], l'impossibilità che la diluizione
concentri, l'invarianza del rapporto zuccheri/acidi, l'assenza di NaN. Se
una di esse cade, è il modello a essere sbagliato, non il test.

Non è un esercizio di stile: una di queste proprietà ha trovato un bug
reale. Un'acidità denormale (10⁻³⁰⁹) non è zero, superava la guardia
`acidity == 0` e faceva traboccare il rapporto zuccheri/acidi a infinito,
che si propagava silenzioso nel profilo restituito. Nessun test a esempio
ci sarebbe arrivato.

Fra i test di integrazione, il più importante confronta il punteggio di
pgvector con `FlavorProfile.cosine_similarity`: il dominio resta
l'implementazione di riferimento, e un'ottimizzazione che restituisce
numeri diversi dall'originale è un bug, non un'ottimizzazione.

I valori attesi dei test a esempio sono calcolati a mano dalle formule, non
copiati da un'esecuzione: un test che fotografa l'output conferma solo che
il codice non è cambiato, non che è corretto.

## Stato

Fatto: dominio, solver, matcher, casi d'uso, persistenza, API, test, CI.

Da fare: il **frontend** Next.js — slider dei target, radar chart del
profilo, esplorazione visuale del grafo dei sapori.

## Comandi

`make help` elenca tutto: migrazioni, seed, lint, type check, shell nei
container, psql, redis-cli.
