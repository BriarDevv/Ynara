# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv && \
    mv /root/.local/bin/uvx /usr/local/bin/uvx

WORKDIR /app

# Copiar manifests primero para cachear la capa de deps
COPY pyproject.toml uv.lock* ./

RUN uv sync --frozen --no-dev || uv sync --no-dev

# Ahora el código
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# Runtime: NO re-sincronizar el venv en `uv run` (ya quedó sincronizado arriba).
# Sin esto, un `uv run` como no-root intentaría tocar cache/red en producción.
# `uv sync` (comando explícito de arriba) no se ve afectado por este flag.
ENV UV_NO_SYNC=1

# Usuario no-root (hardening): si hay un RCE o path-traversal en la app o en una
# dependencia, el proceso NO corre como root dentro del contenedor. Se crea
# DESPUÉS del `uv sync` (que necesita root) y se chownea /app para que el venv,
# el código y el dir de schedule de celery beat queden accesibles por appuser.
# /app/celerybeat existe acá con owner appuser para que el volumen nombrado del
# servicio beat (infra/docker/docker-compose.yml) herede ese owner al crearse.
RUN useradd --system --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/celerybeat \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Liveness/readiness a nivel imagen (complementa el healthcheck del compose): el
# orquestador puede distinguir "vivo" de "roto". /v1/health no toca DB/Redis y
# curl ya está instalado en la imagen.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8080/v1/health || exit 1

# Producción: gunicorn + uvicorn workers
CMD ["uv", "run", "gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8080", \
     "--access-logfile", "-"]
