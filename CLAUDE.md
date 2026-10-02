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
dichiarati `linux/amd64`. `make help` elenca tutti i target; prima di
dichiarare finito: `make check-all`.

Test singolo: `docker compose exec backend uv run pytest tests/unit/test_flavor.py::test_nome -x`.
La copertura si attiva solo con `--cov` (`make test`, `make test-cov`, CI) e
la soglia `fail_under = 85` sta in `[tool.coverage.report]` del
`pyproject.toml`: ha senso solo sull'intera suite, quindi i run parziali
girano senza copertura.

Porte: studio `:3000`, API `:8000` (Swagger su `/docs`), health su `/health`
(fuori da `/api/v1` di proposito). Porte host configurabili nel `.env`.

## Backend

Architettura a layer, vincoli, fisica, solver e test: `backend/CLAUDE.md`.
Un cambio di DTO si riporta anche nel frontend.

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

## Lingua

- **Codice in inglese** (ubiquitous language: entità, campi, metodi,
  messaggi delle eccezioni). Non reintrodurre nomi italiani come `nome` o
  `ingredienti`.
- **Commenti, docstring, documentazione, ADR e messaggi di commit in
  italiano.** I commenti spiegano il *perché* di una scelta (algoritmica,
  fisica, architetturale), come nel codice esistente.
- Etichette dell'interfaccia in italiano da bar (es. "Shakerato"), gli
  identificatori TypeScript restano in inglese.

## Frontend

Convenzioni in `frontend/CLAUDE.md`. Un cambio di DTO sul backend va
riportato a mano in `frontend/src/types/api.ts`.

## Git e CI

- Branch principale `main`: la CI si attiva sui push a `main` e sulle PR.
  Remoto GitHub: `origin` (`petrucciandrea/mixology-engine`).
- **Flusso di lavoro per ogni modifica:**
  1. Prima di toccare il codice, crea un branch da `main` aggiornato, con
     prefisso del tipo di commit: `feat/...`, `fix/...`, `refactor/...`,
     `test/...`, `chore/...`, `docs/...`. Mai lavorare direttamente su `main`.
  2. A modifica conclusa, un commit (o pochi commit coerenti) sul branch,
     con messaggio convenzionale in italiano.
  3. Il merge in `main` avviene **solo con un risultato testato**:
     `make check-all` verde in locale e CI verde sulla PR. Se i controlli
     falliscono, si corregge sul branch; non si fa merge "per sistemare dopo".
  4. Push del branch, PR con `gh pr create` (descrizione in italiano: cosa
     cambia e perché, come è stato verificato), poi merge con
     `gh pr merge --merge` (merge commit, per conservare la storia del
     branch) e aggiornamento di `main` locale.
  5. **I branch non si eliminano**, né in locale né su `origin`: restano come
     storia del lavoro. Mai `--delete-branch`, `git branch -d` o
     `git push origin --delete`.
  6. Niente `push --force` su `main`, niente `--no-verify`.
- Commit convenzionali con soggetto in italiano:
  `feat(matching): ...`, `fix(infra): ...`, `refactor(domain): ...`,
  `test: ...`, `chore: ...`, `build: ...`.
- Prima di dichiarare un lavoro finito: `make check-all` (stessi controlli
  della CI).
- `uv.lock` e `package-lock.json` sono vincolanti (`--frozen`, `npm ci`):
  nuove dipendenze si aggiungono dal container e si committa il lock.
