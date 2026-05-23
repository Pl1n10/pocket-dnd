# pocket-dnd — Dockerfile multi-stage
#
# Stage 1: build del frontend con Node (produce dist/).
# Stage 2: runtime Python con FastAPI + uvicorn. Copia il backend e il dist/
#          buildato accanto, cosi' il backend serve anche la SPA su un'unica
#          porta (vedi DECISIONS.md / Step 9). Un solo container, una sola
#          porta: gira identico su Proxmox/k3s e sul laptop al pub.
#
# Build:    docker build -t pocket-dnd .
# Run:      docker run --rm -p 8000:8000 -v pdnd-data:/data pocket-dnd

# ─────────────────────────── frontend build ───────────────────────────
FROM node:24-alpine AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ─────────────────────────── runtime python ───────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POCKETDND_DB=/data/pocket-dnd.db \
    POCKETDND_STATIC=/app/dist

WORKDIR /app

# deps Python prima del codice: layer cacheato finche' non cambia
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# codice backend + SPA buildata
COPY backend/ /app/
COPY --from=frontend /build/dist /app/dist

# il file SQLite vive in un volume montato in /data
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

# healthcheck con curl (non installato di default su slim): usiamo python
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request,sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)" \
        || exit 1

# entrypoint: --host 0.0.0.0 perche' siamo in container (LAN/Tunnel)
CMD ["sh", "-c", "python3 main.py --host 0.0.0.0 --port 8000 --db ${POCKETDND_DB} --static ${POCKETDND_STATIC}"]
