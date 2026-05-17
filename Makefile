# Makefile — atajos de desarrollo para Ynara
# Probado en Linux/macOS. En Windows usar PowerShell + los scripts/
# equivalentes, o WSL2.

.PHONY: help install install-web install-mobile install-backend \
        dev dev-web dev-mobile dev-backend dev-stack \
        build build-web build-mobile build-backend \
        test test-web test-mobile test-backend \
        lint lint-js lint-py format format-js format-py \
        migrate migrate-create migrate-up migrate-down migrate-check \
        clean reset-memory seed export-user-data \
        docker-dev-up docker-dev-down \
        doctor

help: ## Mostrar esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-22s %s\n", $$1, $$2}'

# ---------- Install ----------

install: ## Instalar todas las dependencias (requiere confirmación humana)
	@echo "TODO: confirmar con humano antes de correr pnpm install + uv sync"
	@echo "Para correr manualmente:"
	@echo "  pnpm install"
	@echo "  cd apps/backend && uv sync"

install-web:
	pnpm --filter web install

install-mobile:
	pnpm --filter mobile install

install-backend:
	cd apps/backend && uv sync

# ---------- Dev ----------

dev: ## Levantar stack completo (web + mobile + backend)
	pnpm dev

dev-web:
	pnpm --filter web dev

dev-mobile:
	pnpm --filter mobile dev

dev-backend:
	cd apps/backend && uv run uvicorn app.main:app --reload --port 8080

dev-stack: docker-dev-up dev-backend ## Redis local + backend

# ---------- Build ----------

build:
	pnpm turbo build

build-web:
	pnpm --filter web build

build-mobile:
	pnpm --filter mobile build

build-backend:
	cd apps/backend && uv build

# ---------- Test ----------

test:
	pnpm turbo test
	$(MAKE) test-backend

test-web:
	pnpm --filter web test

test-mobile:
	pnpm --filter mobile test

test-backend:
	cd apps/backend && uv run pytest

# ---------- Lint / Format ----------

lint: lint-js lint-py

lint-js:
	pnpm biome check .

lint-py:
	cd apps/backend && uv run ruff check .

format: format-js format-py

format-js:
	pnpm biome check --apply .

format-py:
	cd apps/backend && uv run ruff format .

# ---------- Migraciones Alembic ----------

migrate-create: ## Crear nueva migración: make migrate-create m="descripcion"
	cd apps/backend && uv run alembic revision --autogenerate -m "$(m)"

migrate-up:
	cd apps/backend && uv run alembic upgrade head

migrate-down:
	cd apps/backend && uv run alembic downgrade -1

migrate-check:
	cd apps/backend && uv run alembic check

# ---------- Healthcheck pre-PR ----------

doctor: ## Validaciones pre-PR (regla #1 a #5 + landmines). Exit 0 obligatorio antes de PR.
	bash scripts/ynara-doctor.sh

# ---------- Utilidades ----------

clean:
	rm -rf node_modules apps/*/node_modules packages/*/node_modules \
	       apps/*/.next apps/*/dist apps/backend/.venv apps/backend/__pycache__ \
	       .turbo

reset-memory:
	./scripts/reset-memory.sh

seed:
	./scripts/seed-db.sh

export-user-data:
	./scripts/export-user-data.sh

# ---------- Docker dev ----------

docker-dev-up:
	docker compose -f infra/docker/docker-compose.dev.yml up -d

docker-dev-down:
	docker compose -f infra/docker/docker-compose.dev.yml down
