#!/usr/bin/env bash
# Bootstrap inicial del proyecto Ynara.
# - Verifica dependencias del sistema (node, pnpm, python, uv).
# - Copia .env.example a .env donde corresponde.
# - No instala deps (regla #1 de AGENTS.md: requiere confirmación humana).

set -euo pipefail

echo "[init] verificando dependencias del sistema..."

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[init] FALTA: $1"
    exit 1
  fi
  echo "[init]   ok: $1"
}

need node
need pnpm
need python3
need uv
need docker

echo "[init] copiando .env.example → .env donde falten..."

for env_file in \
    ".env" \
    "apps/backend/.env" \
    "apps/web/.env.local" \
    "apps/mobile/.env"; do
  source_example="${env_file}.example"
  # Variantes posibles
  case "$env_file" in
    "apps/web/.env.local") source_example="apps/web/.env.example" ;;
  esac

  if [ ! -f "$env_file" ] && [ -f "$source_example" ]; then
    cp "$source_example" "$env_file"
    echo "[init]   creado $env_file desde $source_example"
  else
    echo "[init]   skip $env_file (ya existe o no hay example)"
  fi
done

echo ""
echo "[init] listo. Próximos pasos (requieren OK humano):"
echo "  1) editar los .env con valores reales (DATABASE_URL de Supabase, etc.)"
echo "  2) pnpm install"
echo "  3) cd apps/backend && uv sync"
echo "  4) docker compose -f infra/docker/docker-compose.dev.yml up -d"
echo "  5) cd apps/backend && uv run alembic upgrade head"
