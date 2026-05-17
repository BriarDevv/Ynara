# apps/backend — Backend de Ynara

FastAPI + Pydantic v2 + SQLAlchemy 2 async + Alembic + Celery + uv.
Cabeza del producto: router LLM, memoria, tools del agente.

## Antes de tocar nada

1. [`../../AGENTS.md`](../../AGENTS.md) — reglas no negociables.
2. [`./AGENTS.md`](./AGENTS.md) — reglas específicas del backend.
3. [`./docs/`](./docs/) — catálogos de models, endpoints, tools y
   política de migraciones.

## Estructura

```
app/
├── api/              # Rutas FastAPI (api/v1/*)
├── core/             # config, security, deps
├── models/           # SQLAlchemy
├── schemas/          # Pydantic request/response
├── services/         # Lógica de negocio (sin framework)
├── llm/              # Router LLM, prompts, tools
│   ├── prompts/
│   └── tools/
├── memory/           # Capas semántica, episódica, procedural
├── workers/          # Celery (tasks)
└── workflows/        # Workflows complejos (consolidación, etc.)

alembic/              # Migraciones
docs/                 # Catálogos vivos
tests/                # Pytest
```

## Scripts

```sh
uv sync                                          # instalar deps
uv run uvicorn app.main:app --reload --port 8080 # dev
uv run pytest                                    # tests
uv run ruff check . && uv run ruff format .      # lint + format
uv run alembic upgrade head                       # migraciones
uv run celery -A app.workers.celery_app worker   # worker async
```

## Variables de entorno

Copiar `.env.example` a `.env`. Crítico:

- `DATABASE_URL` — Postgres (Supabase en MVP).
- `REDIS_URL` — broker + result backend de Celery.
- `GEMMA_ENDPOINT`, `QWEN_ENDPOINT` — vLLM u Ollama.

Detalle: `.env.example`.
