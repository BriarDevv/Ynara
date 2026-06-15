# apps/backend/docs/

Catálogos vivos del backend. Mantener actualizados es parte del PR
correspondiente.

## Archivos

- [`MODELS.md`](./MODELS.md) — modelos SQLAlchemy del proyecto.
- [`ENDPOINTS.md`](./ENDPOINTS.md) — endpoints HTTP.
- [`TOOLS.md`](./TOOLS.md) — tools que Qwen puede llamar.
- [`MIGRATIONS.md`](./MIGRATIONS.md) — política de migraciones
  Alembic.

## Arquitectura y planes

Estos catálogos son el **qué**; el **cómo** vive en otro lado:

- Mapa del código, capa LLM (`app/llm/`) y gates: [`../AGENTS.md`](../AGENTS.md).
- Decisiones: [ADRs](../../../docs/architecture/adrs/) — ADR-002 (dual stack Gemma/Qwen), ADR-005 (Supabase MVP), ADR-009 (serving vLLM + parsers), ADR-013 (LLM_SERVING reemplaza LLM_TOPOLOGY), ADR-014 (motor local 16GB Ollama/GGUF vs vLLM 24GB+).
- Plan de la capa de inferencia: [`LLM-INFERENCE-INTEGRATION.md`](../../../docs/planning/LLM-INFERENCE-INTEGRATION.md).

## Regla

Si agregás un modelo, endpoint, tool o migración, **actualizás el
catálogo correspondiente** en el mismo PR. CI no lo verifica todavía
(TODO), pero la review humana sí.
