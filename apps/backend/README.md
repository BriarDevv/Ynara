# apps/backend — Backend de Ynara

FastAPI + Pydantic v2 + SQLAlchemy 2 async + Alembic + Celery + uv.
Cabeza del producto: **router LLM, memoria y tools del agente**. Toda
inferencia es on-prem (vLLM dual: Gemma conversacional + Qwen agente);
ningún dato de usuario sale del perímetro (regla #4).

## Antes de tocar nada

1. [`../../AGENTS.md`](../../AGENTS.md) — 10 reglas no negociables del repo.
2. [`./AGENTS.md`](./AGENTS.md) — **reglas + mapa operativo del backend** (gates, capa LLM, tests, playbooks). Lectura obligatoria.
3. [`./docs/`](./docs/) — catálogos vivos (models, endpoints, tools, migraciones).

## Estado

- **Construido** (mergeado): capa de inferencia LLM **M0–M6** — config single-source, cliente vLLM resiliente (pool + circuit breaker + fallback on-prem), prompts por modo, framework de tools (calendar + reminder stubs) — y la **migración inicial** (6 tablas, 4 enums, pgvector). DB conectada (Supabase, session pooler).
- **Pendiente**: M7 (`memory.*`, sagrado), M8 (`router.py`), M9 (endpoint `/v1/chat`), auth (`core/security.py`), workers Celery. Ver [`../../docs/planning/LLM-INFERENCE-INTEGRATION.md`](../../docs/planning/LLM-INFERENCE-INTEGRATION.md).

## Estructura

```
app/
├── main.py          # entrypoint FastAPI (lifespan, CORS, routers v1)
├── enums.py         # StrEnums cross-domain (Mode, MemoryLayer, LlmModel, AuditOperation)
├── core/            # config (Settings lazy), deps (engine async), security (auth, TODO)
├── api/v1/          # rutas FastAPI, un archivo por dominio
├── models/          # SQLAlchemy 2 (user, session, memory 🔴, audit 🔴)
├── schemas/         # Pydantic v2 (mirror de models + payloads de API)
├── services/        # lógica de negocio sin framework (deps por argumento)
├── llm/             # capa de inferencia — config, clients/, prompts/, tools/, router (M8)
├── memory/          # 🔴 wrappers de las 3 capas sagradas (M7, TODO)
├── workers/         # Celery (consolidación async)
└── workflows/       # decay/retención/consolidación (TODO)

alembic/             # Migraciones (env.py acepta TEST_DATABASE_URL)
docs/                # Catálogos vivos (MODELS, ENDPOINTS, TOOLS, MIGRATIONS)
tests/               # Pytest async (unit + integration con DB real)
```

Detalle de la capa LLM y los gates: [`./AGENTS.md`](./AGENTS.md).

## Comandos

Canónico con `uv`. Si `uv` no está en PATH (p.ej. Windows), reemplazá
`uv run python` por `.venv\Scripts\python.exe`.

```sh
uv sync                                            # instalar deps (dev: uv sync --extra dev)
uv run uvicorn app.main:app --reload --port 8080   # dev server
uv run pytest                                      # tests (excluye integration)
uv run pytest -m integration                       # tests de DB real (necesita TEST_DATABASE_URL)
uv run ruff check . && uv run ruff format .        # lint + format
uv run alembic upgrade head                        # aplicar migraciones
uv run celery -A app.workers.celery_app worker     # worker async
```

## Variables de entorno

Copiar `.env.example` a `.env` (gitignored). Críticas:

| Var | Para qué |
|---|---|
| `DATABASE_URL` | Postgres (`postgresql+asyncpg://...`). MVP: session pooler de Supabase. |
| `REDIS_URL` | Broker + result backend de Celery. |
| `JWT_SECRET` | Firma de tokens (auth). |
| `LLM_PRIMARY_BASE_URL` / `LLM_SECONDARY_BASE_URL` / `LLM_TOPOLOGY` | Serving vLLM (ADR-009). |
| `TEST_DATABASE_URL` | Solo tests de integración — DB **dedicada**, nunca prod. |
| `MEMORY_ENCRYPTION_MASTER_KEY` | Cifrado de memoria (pendiente, PR C). |

`served_name` (en `models`), parsers, `quantization` y `max_model_len` (en
`llm.serving`) NO van en `.env`: viven en
[`../../ynara.config.json`](../../ynara.config.json).

## Base de datos: dev vs prod

> **Regla de oro:** en desarrollo apuntás a una DB **local**; a la DB de
> **prod** (Supabase) sólo se apunta a propósito. Un guard de arranque
> (`app/core/db_guard.py`, llamado en el lifespan de `app/main.py`) **aborta el
> boot** si la app corre en modo NO-producción contra un host de prod conocido
> sin opt-in explícito. Esto evitó que se repita el incidente del 2026-05-31,
> donde una corrida en dev contra la DB de prod creó y borró un usuario real.

Sólo hay **un** `DATABASE_URL` activo en `.env`. Cambiar entre dev y prod es
cambiar ese valor (y, para prod intencional en dev, setear un flag).

### DEV — DB local (default seguro)

1. **Levantá el Postgres local con pgvector.** Reusá el mismo contenedor que
   los tests de integración (puerto `5433`). Si todavía no lo tenés:

   ```sh
   docker run -d --name ynara-pg -p 5433:5432 \
     -e POSTGRES_PASSWORD=test pgvector/pgvector:pg16
   ```

2. **Creá la DB de dev** `ynara_dev` (una sola vez):

   ```sh
   docker exec ynara-pg psql -U postgres -c "CREATE DATABASE ynara_dev;"
   ```

   Alternativa: reusá directamente la DB de tests `ynara_test` en vez de crear
   `ynara_dev` (ojo: tu data de dev y la de tests compartirían DB).

3. **Apuntá `DATABASE_URL` a la DB local** en tu `.env`:

   ```sh
   DATABASE_URL=postgresql://postgres:test@localhost:5433/ynara_dev
   ```

4. (Primera vez) aplicá las migraciones contra la DB de dev:

   ```sh
   uv run alembic upgrade head     # o: .venv\Scripts\python.exe -m alembic upgrade head
   ```

Con un host local el guard **no se dispara**: la app boota normal.

Atajo de un solo comando: `scripts/run-local.ps1` (Windows) o
`scripts/run-local.sh` (Linux/macOS) exportan ese `DATABASE_URL` de dev y
levantan uvicorn. Ver [`scripts/`](./scripts/).

### PROD — Supabase (intencional)

Hay dos formas, según el caso:

- **Deploy real:** `ENVIRONMENT=production`. El guard nunca aplica y la app
  boota contra prod normalmente (también endurece `JWT_SECRET`, oculta `/docs`,
  etc.).
- **Corrida dev-contra-prod consciente** (debug puntual, sin cambiar
  `ENVIRONMENT`): apuntá `DATABASE_URL` a Supabase **y** activá el opt-in:

  ```sh
  # .env  (o export en la shell)
  DATABASE_URL=postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres
  YNARA_ALLOW_PROD_DB=1
  ```

  Sin `YNARA_ALLOW_PROD_DB=1`, el guard aborta el arranque con este mensaje
  (sólo muestra el **host**, nunca el connection string con credenciales):

  ```text
  RuntimeError: Guard anti-prod: la app está booteando en modo NO-producción
  contra una base de datos que parece de PRODUCCIÓN (host: '...supabase.com').
  Esto fue un incidente real: una corrida en dev contra esta DB creó y borró un
  usuario en producción.

  Qué hacer:
    • Para DEV (lo habitual): apuntá DATABASE_URL a tu Postgres LOCAL, por ej.
        DATABASE_URL=postgresql://postgres:test@localhost:5433/ynara_dev
      (mismo contenedor pgvector de los tests; ver 'Base de datos: dev vs prod'
      en apps/backend/README.md).
    • Si querés correr dev CONTRA PROD a propósito: exportá YNARA_ALLOW_PROD_DB=1
      (corrida consciente, bajo tu responsabilidad).
    • En el deploy de producción esto no aplica: ENVIRONMENT=production boota
      normal.
  ```

### Resumen rápido

| Quiero… | `ENVIRONMENT` | `DATABASE_URL` | `YNARA_ALLOW_PROD_DB` |
|---|---|---|---|
| Dev contra DB local (default) | `development` | `...@localhost:5433/ynara_dev` | (sin setear) |
| Deploy de producción | `production` | Supabase | (sin setear, no aplica) |
| Dev contra prod a propósito | `development` | Supabase | `1` |

Hosts que el guard considera de prod: `*.supabase.co`, `*.supabase.com` y
cualquiera que contenga `pooler.supabase`. Tests bajo pytest nunca disparan el
guard (overridean `get_db` con la DB de tests).
