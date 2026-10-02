# ADR-0010 — Pubblicazione su piani gratuiti: Vercel, Render, Neon, senza Redis

**Stato:** accettata

## Contesto

Il progetto deve essere raggiungibile online, gratis e senza scadenza,
accettando risorse limitate: serve a mostrarlo, non a reggere traffico.
Lo stack di sviluppo (Docker Compose con PostgreSQL/pgvector, Redis,
FastAPI e Next.js) non entra in un hosting condiviso PHP, e nessun piano
gratuito ospita tutti e quattro i servizi insieme.

Tre fatti del codice hanno pesato sulla scelta:

- **Redis serve solo alla cache del grafo delle affinità**, e la cache era
  già progettata per degradare a miss in caso di guasto. Il grafo si
  ricostruisce comunque; la cache fa solo risparmiare tempo.
- **I provider Postgres gestiti forniscono URL in formato libpq**
  (`sslmode`, `channel_binding`), che il dialetto asyncpg di SQLAlchemy
  inoltra ad `asyncpg.connect()`, dove falliscono con un `TypeError`.
- **Il Dockerfile del backend era solo di sviluppo**: compilatori,
  dipendenze di test, `uv run` a ogni avvio, porta fissa.

## Decisione

1. **Topologia.** Frontend su **Vercel** (Hobby), backend su **Render**
   (web service Docker, piano free, Frankfurt), database su **Neon** (free,
   `eu-central-1`, pgvector incluso). Il browser parla solo con Vercel: il
   server Next inoltra `/api/v1` a Render con le rewrite già esistenti
   (`BACKEND_INTERNAL_URL`), quindi niente CORS.
2. **Niente Redis in produzione.** `REDIS_URL` diventa facoltativa; vuota o
   assente, il composition root monta `NullGraphSnapshotCache` e `/health`
   riporta Redis come `disabled`, che non è un guasto. In sviluppo e in CI
   Redis resta attivo, quindi il percorso con la cache resta testato.
   Riattivarlo in produzione richiede solo un URL, non codice.
3. **L'URL del database si normalizza in `Settings`.** Lo schema generico
   diventa `postgresql+asyncpg`, `sslmode` diventa `ssl` e `channel_binding`
   si toglie. App, Alembic e seed leggono tutti da lì, quindi la stringa di
   Neon si incolla così com'è. Si usa l'endpoint **diretto**, non
   `-pooler`: PgBouncer in transaction mode e i prepared statement di
   asyncpg non vanno d'accordo, e con una sola istanza il pool
   dell'applicazione basta.
4. **Immagine di produzione multi-stage.** Lo stage `runtime` è l'ultimo
   del Dockerfile, quindi il default: Render non permette di scegliere un
   `--target`. Niente uv né compilatori, utente non root, porta da `$PORT`,
   `ENV=production` e `DEBUG=false` di default. Compose sceglie
   esplicitamente lo stage `dev`.
5. **Prima lo schema, poi il codice.** Render non fa il deploy al push
   (`autoDeployTrigger: off` in `render.yaml`). Lo avvia il workflow
   `Deploy` quando la CI del backend su `main` è verde: migrazioni su Neon,
   seed idempotente, poi deploy hook con `ref` sul commit migrato. Il piano
   free di Render non ha shell né comandi di pre-deploy, e un workflow
   versionato è comunque più ripetibile di un comando lanciato a mano. I
   secret stanno nell'environment GitHub `production`.

## Conseguenze

Misure prese in locale sull'immagine di produzione con i limiti del piano
free di Render (`--cpus=0.1 --memory=512m`), dispensa del seed (86
ingredienti, 58 ricette):

| Operazione | Tempo |
|---|---|
| Avvio del processo (fino a "startup complete") | ~27 s |
| Profilo di una ricetta salvata | ~12 ms |
| Ottimizzazione (solver, convergente) | ~1,2 s |
| Sostituti (pgvector) | ~0,2 s |
| Abbinamenti (grafo ricostruito, senza cache) | ~0,8 s |
| Panoramica del grafo e comunità | ~1,6 s |

Memoria a regime: circa 106 MB su 512.

- **Il primo accesso dopo una pausa è lento.** Render sospende il servizio
  dopo 15 minuti senza traffico; al risveglio si somma il riavvio della
  piattaforma (circa un minuto, secondo Render) all'avvio del processo.
  Prima di una presentazione conviene aprire lo studio qualche minuto
  prima. Non è documentato se le rewrite esterne di Vercel attendano così
  a lungo: va misurato dopo il primo rilascio, ed eventualmente risolto con
  un ping periodico o un messaggio d'attesa nello studio.
- **Senza cache il matcher paga la ricostruzione del grafo** a ogni
  richiesta: circa 0,8 s su 0,1 CPU, contro circa 80 ms con una CPU intera.
  Con questa dispensa è accettabile. Con un catalogo molto più grande
  conviene riattivare Redis (per esempio Upstash): basta un URL.
- **`channel_binding` si perde.** La connessione resta cifrata (TLS) e
  autenticata con SCRAM, ma senza binding al canale, che asyncpg non
  supporta.
- **Vercel Hobby è solo per uso non commerciale**: va bene per un
  progetto dimostrativo, non per un prodotto.
- **Il seed gira a ogni rilascio.** È idempotente e non duplica nulla, ma
  sui classici che conosce non è neutro: riporta sempre il ghiaccio di
  servizio al valore del seed, e per le ricette in `REVISED` (Gimlet,
  Bloody Mary) anche dosi e istruzioni. Bicchiere e famiglia li imposta
  solo dove mancano. Una modifica fatta dallo studio a quei campi di un
  classico verrebbe annullata al rilascio successivo. Per una vetrina va
  bene, perché i classici devono restare quelli di riferimento; se lo
  studio pubblico diventasse un luogo di lavoro, il seed andrebbe tolto
  dal workflow e lanciato solo a mano.
- Frontend e backend si rilasciano in modo indipendente. Un cambio di DTO
  che tocca entrambi può restare disallineato per i minuti fra i due
  rilasci; per un progetto dimostrativo è un compromesso accettabile.
