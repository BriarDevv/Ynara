#!/usr/bin/env bash
# run-local.sh — levanta el backend contra la DB de DEV LOCAL (Linux/macOS).
#
# Atajo para que cambiar a dev sea UN comando: exporta un DATABASE_URL local
# (sin tocar tu .env) y arranca uvicorn con reload. El guard anti-prod
# (app/core/db_guard.py) no se dispara porque el host es localhost.
#
# Uso (desde apps/backend):
#   ./scripts/run-local.sh
#   DEV_DATABASE_URL='...' ./scripts/run-local.sh   # override puntual
#
# Requiere un Postgres con pgvector en :5433 y la DB creada (ver
# "Base de datos: dev vs prod" en README.md).
set -euo pipefail

# DB de dev local por default; overridable con DEV_DATABASE_URL.
DEV_URL="${DEV_DATABASE_URL:-postgresql://postgres:test@localhost:5433/ynara_dev}"

export DATABASE_URL="$DEV_URL"
export ENVIRONMENT="development"
# Cinturón y tiradores: nunca arrastrar un opt-in de prod a una corrida local.
unset YNARA_ALLOW_PROD_DB || true

echo "[run-local] DATABASE_URL -> $DEV_URL"
echo "[run-local] ENVIRONMENT  -> development"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$SCRIPT_DIR/../.venv/bin/python"

if [ -x "$VENV_PY" ]; then
    exec "$VENV_PY" -m uvicorn app.main:app --reload --port 8080
else
    exec uv run uvicorn app.main:app --reload --port 8080
fi
