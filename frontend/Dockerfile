# syntax=docker/dockerfile:1

# ------------------------------------------------------------------
# Mixology Engine — Frontend Dockerfile
# Target esplicito linux/amd64 per coerenza con il backend e con la
# macchina di sviluppo (Mac Intel x86_64).
# ------------------------------------------------------------------
FROM --platform=linux/amd64 node:22-slim AS deps

WORKDIR /app

# Prima solo i manifest, per sfruttare la cache dei layer: `npm ci` viene
# ri-eseguito solo quando cambiano package.json o package-lock.json.
# `ci` e non `install`: rispetta il lock alla lettera e fallisce se e'
# disallineato, invece di aggiornarlo in silenzio.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# ------------------------------------------------------------------
FROM deps AS build

COPY . .
# L'URL dell'API viene inlinato nel bundle a build time: le variabili
# NEXT_PUBLIC_* non esistono piu' a runtime nel browser.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

# ------------------------------------------------------------------
FROM --platform=linux/amd64 node:22-slim AS runtime

WORKDIR /app
ENV NODE_ENV=production

# L'output `standalone` porta con se' solo i moduli davvero usati: qui non
# serve copiare node_modules, che e' la parte piu' pesante dell'immagine.
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public

EXPOSE 3000
ENV HOSTNAME=0.0.0.0 PORT=3000

CMD ["node", "server.js"]
