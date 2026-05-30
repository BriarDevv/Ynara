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
