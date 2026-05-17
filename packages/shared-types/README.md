# @ynara/shared-types

Types TypeScript compartidos entre `apps/web` y `apps/mobile`.

> No incluye lógica ni schemas Zod — solo `type` y `interface`. Para
> schemas validables ver [`@ynara/shared-schemas`](../shared-schemas/).

## Convención

- La fuente de verdad de los modelos del dominio sigue siendo
  Pydantic en `apps/backend/`. Estos types son **derivados** y deben
  mantenerse coherentes manualmente (o vía codegen en el futuro,
  TODO).
- Sin dependencias externas. Solo `type` puro de TS.
