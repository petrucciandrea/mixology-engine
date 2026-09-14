.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help init up up-build down restart logs logs-backend ps \
        test test-cov lint lint-fix format typecheck check \
        migrate migrate-down makemigrations \
        shell backend-shell db-shell redis-cli clean

help: ## Mostra questo elenco di comandi
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

init: ## Crea .env da .env.example se non esiste già
	@test -f .env || cp .env.example .env
	@echo "✅ .env pronto. Modificalo se necessario, poi esegui 'make up'."

up: ## Avvia lo stack in background (build inclusa se necessaria)
	$(COMPOSE) up -d --build

up-build: ## Forza il rebuild completo delle immagini e avvia lo stack
	$(COMPOSE) up -d --build --force-recreate

down: ## Ferma e rimuove i container (i volumi dati restano)
	$(COMPOSE) down

restart: down up ## Riavvia l'intero stack

logs: ## Segue i log di tutti i servizi
	$(COMPOSE) logs -f

logs-backend: ## Segue i log del solo backend
	$(COMPOSE) logs -f backend

ps: ## Stato dei container (incluso health status)
	$(COMPOSE) ps

test: ## Esegue la suite Pytest dentro il container backend
	$(COMPOSE) exec backend uv run pytest

test-cov: ## Esegue i test con report di coverage
	$(COMPOSE) exec backend uv run pytest --cov=app --cov-report=term-missing

lint: ## Controlla lo stile del codice con Ruff (nessuna modifica)
	$(COMPOSE) exec backend uv run ruff check .

lint-fix: ## Corregge automaticamente le violazioni Ruff risolvibili
	$(COMPOSE) exec backend uv run ruff check --fix .

format: ## Formatta il codice con Ruff
	$(COMPOSE) exec backend uv run ruff format .

typecheck: ## Type-check statico con MyPy (strict mode)
	$(COMPOSE) exec backend uv run mypy app

check: lint typecheck test ## Pipeline completa: lint + typecheck + test

migrate: ## Applica tutte le migrazioni Alembic pendenti (upgrade head)
	$(COMPOSE) exec backend uv run alembic upgrade head

migrate-down: ## Rollback di una revisione Alembic
	$(COMPOSE) exec backend uv run alembic downgrade -1

makemigrations: ## Genera una nuova revisione Alembic (uso: make makemigrations m="messaggio")
	$(COMPOSE) exec backend uv run alembic revision --autogenerate -m "$(m)"

shell: backend-shell ## Alias di backend-shell

backend-shell: ## Apre una shell bash nel container backend
	$(COMPOSE) exec backend bash

db-shell: ## Apre psql sul database applicativo
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-mixology} -d $${POSTGRES_DB:-mixology_engine}

redis-cli: ## Apre redis-cli sul container redis
	$(COMPOSE) exec redis redis-cli

clean: ## Rimuove container, network e volumi (⚠️ cancella i dati del DB)
	$(COMPOSE) down -v --remove-orphans
