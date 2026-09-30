# Technical Architecture & Roadmap

## Tech Stack
- **Backend:** Python 3.12, FastAPI, Pydantic v2
- **Solver & Math:** SciPy (`scipy.optimize`), NumPy, NetworkX (Graph Theory)
- **Database:** PostgreSQL con estensione `pgvector` (Vector Search profili organolettici) + Redis (Cache)
- **Frontend:** Next.js (App Router), TypeScript (Strict), Tailwind CSS, shadcn/ui, Recharts / D3.js
- **Testing & QA:** Pytest, Hypothesis (Property-based testing), Ruff, MyPy

## Architettura Monorepo (Clean Architecture)
```text
mixology-engine/
├── backend/
│   ├── app/
│   │   ├── domain/        # Entità pure: Ingredient, Recipe, PhysicalProfile
│   │   ├── application/   # BalancingSolver (SciPy), FlavorGraphMatcher
│   │   ├── infrastructure/# Repositories PostgreSQL/pgvector, Redis cache
│   │   └── api/           # Router FastAPI, Schemi DTO Pydantic
│   └── tests/             # Pytest e test Hypothesis
├── frontend/
│   └── src/
│       ├── components/    # Sliders, Radar Chart sapore, Drink Canvas
│       ├── hooks/         # Gestione stato ricetta reattivo
│       └── types/         # Tipi TypeScript
└── docs/                  # Specifiche molecolari e formule

## Decisioni Architetturali Confermate (ADR)
1. **Solver SciPy:** Problema non-lineare vincolato risolto con `scipy.optimize.minimize(method='SLSQP')` e bounds volumetrici fissi. Il solver calcola i volumi $V_i$ dati gli ingredienti; la selezione ingredienti è demandata al Matcher vettoriale/grafo.
2. **Concorrenza CPU-bound:** Utilizzo di `asyncio.to_thread` nei service layer di FastAPI per isolare i calcoli di SciPy dall'event loop asincrono.
3. **pgvector & profilo organolettico:** Vettore a 32 descrittori espliciti (tassonomia in `domain/flavor.py`, non embedding di un modello linguistico) per la similarity search del coseno usata nella sostituzione; l'abbinamento usa il grafo delle affinità NetworkX. Vedi ADR-0005 e ADR-0007.
4. **Database Migrations:** Adozione formale di **Alembic** con driver async (`asyncpg`) per SQLAlchemy.