# INSTALL.md — Instalación inicial

> Esta guía cubre la **primera vez** que se levanta el repo en una
> máquina. Para el día a día ver
> [`LOCAL-DEV.md`](./LOCAL-DEV.md).

## Pre-requisitos

- Node.js 20+
- pnpm 10+ (`corepack enable && corepack prepare pnpm@latest --activate`)
- Python 3.12+
- uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker + Docker Compose (para Redis local y dev del backend)
- (Opcional pero recomendado) GPU NVIDIA + CUDA 12.x para correr
  vLLM localmente.

## Pasos

### 1. Clonar y ubicar

```sh
git clone <repo-url> ynara
cd ynara
```

### 2. Leer el contrato

Antes de cualquier instalación, leer:
- `AGENTS.md`
- `apps/backend/AGENTS.md` (si vas a tocar backend)
- `apps/web/AGENTS.md` (si vas a tocar web)
- `apps/mobile/AGENTS.md` (si vas a tocar mobile)

### 3. Crear el proyecto en Supabase (fase MVP)

1. Crear proyecto en supabase.com.
2. Habilitar la extensión `pgvector`: Dashboard → Database →
   Extensions → buscar `vector` → enable.
3. Tomar nota del `DATABASE_URL` desde Settings → Database →
   Connection string → URI.

Esto es **manual** y requiere confirmación humana. No automatizar
todavía.

### 4. Configurar variables de entorno

```sh
cp .env.example .env
cp apps/backend/.env.example apps/backend/.env
cp apps/web/.env.example apps/web/.env.local
cp apps/mobile/.env.example apps/mobile/.env
```

Editar a mano cada `.env` con los valores reales (DATABASE_URL de
Supabase, etc.). **Nunca commitearlos**.

### 5. Instalar dependencias (requiere confirmación humana)

```sh
# Frontend + tooling (regla #1)
pnpm install

# Backend (regla #1)
cd apps/backend && uv sync && cd -

# Pre-commit (opcional)
pipx install pre-commit
pre-commit install
```

### 6. Levantar Redis local (Docker)

```sh
make docker-dev-up
# o:
docker compose -f infra/docker/docker-compose.dev.yml up -d
```

### 7. Aplicar migraciones contra Supabase

> Antes de la primera migración con embeddings, verificar que
> pgvector esté habilitado en el dashboard de Supabase.

```sh
cd apps/backend
uv run alembic upgrade head
```

### 8. Levantar backend

```sh
make dev-backend
# o:
cd apps/backend && uv run uvicorn app.main:app --reload --port 8080
```

### 9. Levantar web

```sh
make dev-web
# o:
pnpm --filter web dev
```

### 10. (Opcional) Levantar mobile

```sh
pnpm --filter mobile dev
```

## Próximos pasos

- Crear el primer usuario de prueba: `make seed`.
- Configurar vLLM: ver `infra/vllm/README.md`.
