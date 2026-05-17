# apps/backend/docs/

Catálogos vivos del backend. Mantener actualizados es parte del PR
correspondiente.

## Archivos

- [`MODELS.md`](./MODELS.md) — modelos SQLAlchemy del proyecto.
- [`ENDPOINTS.md`](./ENDPOINTS.md) — endpoints HTTP.
- [`TOOLS.md`](./TOOLS.md) — tools que Qwen puede llamar.
- [`MIGRATIONS.md`](./MIGRATIONS.md) — política de migraciones
  Alembic.

## Regla

Si agregás un modelo, endpoint, tool o migración, **actualizás el
catálogo correspondiente** en el mismo PR. CI no lo verifica todavía
(TODO), pero la review humana sí.
