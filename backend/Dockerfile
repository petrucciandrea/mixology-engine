# syntax=docker/dockerfile:1

# ------------------------------------------------------------------
# Mixology Engine — Backend Dockerfile
# Target esplicito linux/amd64 per compatibilità Mac Intel x86_64
# e per garantire riproducibilità in eventuali pipeline CI su runner amd64.
# ------------------------------------------------------------------
FROM --platform=linux/amd64 python:3.12-slim-bookworm

# Dipendenze di sistema minime:
# - build-essential/libpq-dev: compilazione asyncpg/psycopg se serve wheel da sorgente
# - curl: healthcheck e installazione uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installazione uv (package manager) tramite immagine ufficiale distroless-style
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copiamo prima i manifest per sfruttare la cache dei layer Docker:
# `uv sync` viene ri-eseguito solo se pyproject.toml/uv.lock cambiano.
# `--frozen` impone il rispetto del lock: la build fallisce se il lock
# non e' allineato al pyproject, invece di risolvere silenziosamente
# versioni diverse da quelle testate in locale.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Copiamo il resto del codice sorgente (montato comunque a runtime via volume
# in dev per l'hot-reload; qui serve per build "standalone" e per CI/test).
COPY . .
RUN uv sync --frozen

EXPOSE 8000

# In sviluppo il comando reale viene sovrascritto da docker-compose.yml
# (con --reload e volumi montati). Questo CMD serve come default "production-like".
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
