# Mixology Engine

Piattaforma enterprise per la creazione e il bilanciamento scientifico di cocktail d'autore
(Clean Architecture, DDD, ottimizzazione vincolata, RAG per il matching di ingredienti).

## Quickstart (Docker-first, Mac Intel x86_64)

```bash
make init      # crea .env da .env.example
make up        # build + avvio db (pgvector) + redis + backend
make ps        # verifica che tutti i container siano "healthy"
make test      # smoke test: conferma che backend, db e redis comunicano
```

API disponibile su http://localhost:8000 — Swagger UI su http://localhost:8000/docs
Health check: http://localhost:8000/health

## Comandi utili

Esegui `make help` per l'elenco completo dei comandi disponibili
(migrazioni Alembic, lint, typecheck, shell nei container, ecc.).

## Struttura

Vedi `TECH_ARCHITECTURE.md` e `DOMAIN_MODEL_AND_MATH.md` nella project knowledge
per lo stack tecnico completo e le formule di dominio (bilanciamento, diluizione
termodinamica secondo il modello di Dave Arnold).
