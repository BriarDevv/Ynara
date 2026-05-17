# docs/operations/ — Operar Ynara

Cómo se instala, se corre en local, se deploya y se mantiene.

## Archivos

- [`INSTALL.md`](./INSTALL.md) — instalación inicial del repo.
- [`LOCAL-DEV.md`](./LOCAL-DEV.md) — flujo de desarrollo diario.
- [`DEPLOY.md`](./DEPLOY.md) — deploy de web, mobile y backend.
- [`RUNBOOK.md`](./RUNBOOK.md) — incidentes comunes y cómo
  responder.
- [`MIGRATION-SUPABASE-TO-SELFHOSTED.md`](./MIGRATION-SUPABASE-TO-SELFHOSTED.md)
  — plan de migración de DB de MVP a V2.

## Antes de levantar nada

1. Leer `../../AGENTS.md` (reglas no negociables).
2. Confirmación humana antes de `pnpm install` y `uv sync` (regla
   #1).
3. Tener creado el proyecto en Supabase con pgvector habilitado
   (durante fase MVP).
