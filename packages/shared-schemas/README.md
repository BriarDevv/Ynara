# @ynara/shared-schemas

Schemas Zod compartidos entre `apps/web` y `apps/mobile` para
validación de inputs (forms, parseo de respuestas).

> Source of truth de los modelos del dominio sigue siendo Pydantic
> en `apps/backend/`. Estos schemas son derivados. Cualquier
> divergencia es un bug; cerrar coherencia con un PR.

## Stack

- Zod v3 (la versión exacta vive en `package.json`).

## Convención

- Un archivo por dominio (`chat.ts`, `memory.ts`, `auth.ts`).
- Exportar `Schema` (Zod) + `type Inferred = z.infer<typeof Schema>`
  para que el resto del código TS use el type sin re-derivar.
