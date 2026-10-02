# syntax=docker/dockerfile:1

# ------------------------------------------------------------------
# Mixology Engine — Backend Dockerfile
# Target esplicito linux/amd64 per compatibilità Mac Intel x86_64
# e per garantire riproducibilità in eventuali pipeline CI su runner amd64.
#
# Tre stage, come per il frontend:
#   dev      — l'immagine di sviluppo, scelta da docker-compose.yml;
#   builder  — risolve le sole dipendenze di produzione;
#   runtime  — l'immagine di produzione (ADR-0010). È l'ultimo stage, quindi
#              il default di un `docker build` senza `--target`: chi
#              costruisce senza dire nulla ottiene l'immagine da rilasciare,
#              non quella con compilatori e strumenti di test.
# ------------------------------------------------------------------
FROM --platform=linux/amd64 python:3.12-slim-bookworm AS dev

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
# (con --reload e volumi montati).
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ------------------------------------------------------------------
FROM --platform=linux/amd64 python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/

# Il bytecode si compila qui, una volta, invece che al primo import di
# ogni avvio a freddo: su un piano gratuito che sospende il servizio dopo
# pochi minuti di inattività, l'avvio a freddo è il caso normale.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Niente compilatori: numpy, scipy e asyncpg hanno wheel manylinux per
# amd64. Se una dipendenza futura non ne avesse, la build fallirebbe qui,
# che è il posto giusto per scoprirlo.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ------------------------------------------------------------------
FROM --platform=linux/amd64 python:3.12-slim-bookworm AS runtime

# Default sicuri: un'immagine di produzione avviata senza configurazione
# non deve esporre traceback. Il pannello di deploy può comunque
# sovrascriverli.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    ENV=production \
    DEBUG=false

RUN useradd --system --uid 10001 --no-create-home app

WORKDIR /app

# Il venv resta in /app/.venv come nel builder: gli script dentro `bin/`
# hanno shebang assoluti, e spostarlo li romperebbe. Stessa immagine base,
# quindi anche il link all'interprete resta valido.
COPY --from=builder /app/.venv /app/.venv

# Solo ciò che serve a servire e a manutenere il database: niente test.
# Alembic e il seed restano nell'immagine per poterli lanciare da qui
# contro il database di produzione, se servisse farlo a mano.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

USER app

EXPOSE 8000

# Forma shell per leggere `$PORT`, che le piattaforme gestite (Render)
# assegnano a runtime; `exec` lascia uvicorn come PID 1, così riceve
# SIGTERM e chiude i pool in modo ordinato. Il TLS termina sul proxy della
# piattaforma: `--proxy-headers` fa vedere all'app lo schema e l'IP reali.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
