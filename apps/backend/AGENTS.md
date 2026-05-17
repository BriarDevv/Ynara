# apps/backend/AGENTS.md — Reglas del backend

> Fuente canónica del repo: [`../../AGENTS.md`](../../AGENTS.md).

## Reglas duras (resumen)

1. **Tablas sagradas de memoria** (regla #3). Cualquier toque a
   `semantic_memory`, `episodic_memory`, `procedural_memory` requiere
   tests + 2 aprobaciones humanas. Migraciones que las afecten
   también.
2. **Datos de usuario nunca salen del perímetro** (regla #4). Sin
   llamadas a OpenAI, Anthropic, Google APIs. Toda inferencia en
   vLLM/Ollama local.
3. **Autorización en FastAPI** (regla #5). RLS de Supabase no se
   usa como mecanismo primario.
4. **Confirmación humana** para `uv add`, `alembic upgrade head` en
   producción, cambios a `pyproject.toml` mayores.

## Patrones

- **Async-first**: `async def` en rutas y servicios. SQLAlchemy 2
  async (`AsyncSession`).
- **Pydantic v2 strict** en schemas. Sin `Any` salvo justificación
  puntual.
- **Type hints completos**.
- **Services sin framework**: la lógica de negocio en `app/services/`
  no importa nada de FastAPI ni de SQLAlchemy directamente — recibe
  dependencias por argumento. Esto facilita test.
- **Consolidación de memoria siempre async** (Celery). Nunca en el
  path de respuesta.
- **Router LLM** (`app/llm/router.py`) decide modelo según modo.
  Gemma solo lee memoria; Qwen lee+escribe (ADR-002).

## Migraciones

Ver [`docs/MIGRATIONS.md`](./docs/MIGRATIONS.md).

- Naming: `YYYYMMDD_HHMM_descripcion.py`.
- Una migración = un cambio lógico.
- `downgrade()` siempre.
- Tablas sagradas → review humano + 2 aprobaciones.

## Tests

- Pytest async (`pytest-asyncio`).
- **Integración con DB real**, sin mocks (regla del equipo: mocks de
  DB ocultan bugs de migración).
- `tests/conftest.py` arma fixtures con DB de tests separada.

## Layout

- `app/api/v1/*.py` — un archivo por dominio (`health.py`,
  `chat.py`, `memory.py`, ...).
- `app/services/*.py` — lógica de negocio.
- `app/llm/router.py` — único punto de entrada al LLM.
- `app/memory/{semantic,episodic,procedural}.py` — wrappers de cada
  capa.

## Cuando agregar un endpoint

1. Schema Pydantic en `app/schemas/`.
2. Modelo SQLAlchemy si es nuevo (en `app/models/`).
3. Service en `app/services/` con la lógica.
4. Ruta en `app/api/v1/`.
5. Test de integración en `tests/`.
6. Documentar en `docs/ENDPOINTS.md`.
