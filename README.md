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
make check-all # lint + type check + 194 test, backend e frontend
```

Studio su <http://localhost:3000>, API su <http://localhost:8000>, Swagger
su <http://localhost:8000/docs>, health check su <http://localhost:8000/health>.

Se una di quelle porte è già occupata da un altro progetto, cambia
`POSTGRES_HOST_PORT`, `BACKEND_PORT` o `FRONTEND_PORT` nel `.env`: la rete
interna ai container non ne risente.

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
  Campari             0.0634  — compare insieme a Vermouth Rosso in ricette esistenti
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

## Lo studio

L'interfaccia è un banco di lavoro, non un modulo da compilare: si sceglie
un ingrediente dalla dispensa, si muovono gli slider, e ogni misura si
aggiorna mentre la mano è ancora sul cursore.

* **Drink canvas** — il bicchiere disegnato a bande proporzionali ai volumi,
  colorate per famiglia merceologica, con l'acqua di fusione come banda a
  sé. Si legge la ricetta dalle proporzioni prima di leggere i nomi.
* **Lettura del bilanciamento** — ABV finale in grande perché è il numero
  per cui si guarda il pannello, poi Brix, acidità e alcol puro. Il rapporto
  zuccheri/acidi è su una scala con la finestra dei sour evidenziata: il
  numero da solo non dice nulla a chi non la ha in testa, la posizione sì.
* **Radar aromatico** — le famiglie più presenti nella miscela, su asse
  fisso da 0 a 1 perché due drink di intensità diversa non devono disegnare
  la stessa forma.
* **Solver** — si digitano i target, si legge lo stato di convergenza e il
  residuo per obiettivo, e solo se convince si applica il dosaggio proposto.
* **Matcher** — abbinamenti e sostituti in due schede separate, perché sono
  meccanismi diversi. Ogni sostituto mostra i due assi separati e le
  avvertenze su cosa cambia nel drink.

Lo stato della ricetta vive in un hook (`useRecipe`) che accorpa i movimenti
di slider prima di interrogare il backend e scarta le risposte arrivate
fuori ordine: senza, i numeri rimbalzerebbero mentre la mano è ferma.

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

frontend/src/
├── types/           Contratto HTTP tipizzato
├── lib/             Client API, formattazione delle misure
├── hooks/           useRecipe: stato reattivo e chiamate accorpate
└── components/
    ├── ui/                Primitive (Radix + CVA, stile shadcn)
    └── studio/            Canvas, radar, slider, pannelli solver e matcher
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

Fatto anche il **frontend**: Next.js App Router, TypeScript strict,
Tailwind v4, Recharts, primitive Radix in stile shadcn/ui.

Il pezzo che manca è l'**esplorazione visuale del grafo dei sapori**: gli
endpoint `/match/graph` e `/match/bridge` sono pronti e non hanno ancora
una rappresentazione — è il candidato naturale per una vista D3 a rete.

## Pubblicazione

Online gratis, senza scadenza, su tre servizi (ADR-0010):

| Pezzo | Servizio | Note |
|---|---|---|
| Studio (Next.js) | Vercel Hobby | inoltra `/api/v1` al backend, niente CORS |
| API (FastAPI) | Render free, Docker | si sospende dopo 15 minuti senza traffico |
| PostgreSQL + pgvector | Neon free | endpoint diretto, non `-pooler` |

Redis in produzione non c'è: la cache del grafo è nulla e `/health`
riporta `"redis": "disabled"`.

Il rilascio del backend lo fa il workflow **Deploy**: quando la CI del
backend su `main` è verde applica le migrazioni a Neon, lancia il seed e
solo dopo chiama il deploy hook di Render. Il frontend lo rilascia Vercel
a ogni push su `main`.

### Prima configurazione

1. **Neon.** Crea un progetto Postgres 16 in `eu-central-1` e copia la
   stringa di connessione **diretta**. Non serve modificarla: `sslmode` e
   `channel_binding` li normalizza `Settings`.
2. **GitHub.** In *Settings → Environments* crea l'environment
   `production` con il secret `PRODUCTION_DATABASE_URL` (la stringa di
   Neon). Lancia a mano il workflow **Deploy** (*Actions → Deploy → Run
   workflow*): crea lo schema e popola la dispensa. L'ultimo passo fallirà
   perché manca ancora il deploy hook, ed è previsto.
3. **Render.** *New → Blueprint* su questo repository: legge
   `render.yaml` e chiede `DATABASE_URL` (la stessa stringa). Dalle
   impostazioni del servizio copia il *Deploy Hook* nel secret
   `RENDER_DEPLOY_HOOK_URL` dell'environment `production`.
4. **Vercel.** Importa il repository con *Root Directory* `frontend` e la
   variabile `BACKEND_INTERNAL_URL=https://<servizio>.onrender.com`.
   Serve già in fase di build, perché le rewrite si fissano lì.
5. **Verifica.** `https://<servizio>.onrender.com/health` deve rispondere
   `ok`; dall'URL di Vercel lo studio deve bilanciare un Daiquiri.

Per provare in locale l'immagine che va in produzione:

```bash
docker build -t mixology-backend:prod backend   # stage runtime, il default
docker run --rm --network mixology-engine_default -p 10000:10000 \
  -e PORT=10000 -e REDIS_URL= \
  -e DATABASE_URL=postgresql+asyncpg://mixology:mixology_dev_pw@db:5432/mixology_engine \
  mixology-backend:prod
```

## Comandi

`make help` elenca tutto: migrazioni, seed, lint, type check, shell nei
container, psql, redis-cli.
