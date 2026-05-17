# AI-GUIDELINES.md — Reglas extendidas para IAs (y humanos)

Las 10 reglas **no negociables** viven en `AGENTS.md`. Estas son 15
reglas extendidas que sirven como guía operativa adicional.

## Estilo y tipos

1. **TypeScript strict siempre.** `strict: true` en `tsconfig.json`.
   Prohibido `any` salvo en boundaries muy puntuales con justificación
   en comentario.
2. **Pydantic v2 strict y type hints completos** en Python. Prohibido
   `Any` salvo en boundaries.
3. **Archivos chicos.** Target menos de 300 líneas por archivo;
   refactor obligatorio si pasa de 500.
4. **Naming**:
   - Python: `snake_case` para variables y funciones, `PascalCase` para
     clases.
   - TypeScript: `camelCase` para variables y funciones, `PascalCase`
     para tipos y componentes React.
   - Archivos Next.js: `kebab-case` para rutas y componentes;
     `PascalCase.tsx` solo si es un componente principal en su carpeta.
5. **Imports ordenados**: stdlib → terceros → propios. Auto-fix con
   Biome (JS/TS) y Ruff (Python).

## Arquitectura

6. **Stack definido en ADRs.** Cualquier desviación (cambiar Next por
   Remix, agregar Mongo, cambiar Mem0 por X) requiere ADR nuevo
   aprobado **antes** del PR de implementación.
7. **Modelos con roles fijos.** Gemma solo lee memoria, Qwen lee y
   escribe (ADR-002). No mezclar.
8. **Postgres + pgvector es la única DB.** No introducir Mongo,
   Pinecone, Qdrant, Neo4j, Redis para datos persistentes (Redis solo
   para cache + broker). Requiere ADR (ADR-004).
9. **Consolidación de memoria siempre async.** Nunca en el path de
   respuesta al usuario. Workers Celery.
10. **Auth y autorización viven en FastAPI.** Prohibido RLS de
    Supabase como primario (ADR-005, regla #5 de AGENTS).

## Testing y calidad

11. **Tests primero o junto al código.** Toda función pública con
    test unitario. Toda ruta crítica con test de integración. Tests
    de memoria y migraciones obligatorios.
12. **Skills en `skills/` con formato Anthropic.** Cualquier workflow
    repetitivo se documenta como SKILL.md.

## Diseño y UX

13. **`DESIGN.md` está vacío hasta aprobación del equipo.** Mientras
    tanto, usar tokens genéricos de Tailwind. **No hardcodear colores
    ni tipografías** en componentes — siempre vía CSS variables / theme.
14. **Tono por modo** según `ynara.config.json`. En modos
    conversacionales (Bienestar, Vida, Estudio): **nunca clínico,
    nunca moralizante**.

## Cultura del repo

15. **En caso de duda, preguntar antes de inventar.** El proyecto
    está en fase temprana y muchas decisiones siguen abiertas. Si
    ves un TODO, un placeholder, una ambigüedad: pedí aclaración
    humana. Inventar y meter una decisión sin discusión es peor que
    la pausa de pedir.

## Anti-patterns

Cosas que **no** queremos ver en el repo:

- Mocks de DB en tests de migraciones o de memoria.
- Imports de `@supabase/supabase-js` en `apps/web/` o `apps/mobile/`.
- Llamadas a APIs de OpenAI/Anthropic/Google desde el backend.
- Secrets hardcodeados.
- Tipos `any` sin justificación.
- Archivos de 1500 líneas.
- Comentarios que repiten el código ("// incrementa i").
- Emojis en código o docs.
- Patrones medio implementados ("agregamos esto por las dudas").

## Landmines aprendidas

Cosas concretas que ya nos hicieron tropezar (o que sabemos que van
a hacerlo). El `AGENTS.md` las menciona corto; acá va el detalle de
cada una. Si tocás los archivos asociados, **leé esta sección primero**.

### gitignore — anclar patrones de carpetas comunes

`models/` (sin slash inicial) matchea **cualquier** carpeta `models`
del árbol. Eso ocultó `apps/backend/app/models/` (módulo Python
legítimo con `Base`, `TimestampMixin`, `UUIDPKMixin`) durante el
scaffold inicial. El módulo se commiteó solo después del fix
`fix: anclar gitignore de models/ y checkpoints/ a root del repo`.

Patrones que tienen que quedar **anclados a root** (`/...`) en
`.gitignore`:

- `/models/` — pesos descargados de HuggingFace, no el módulo Python.
- `/checkpoints/` — checkpoints de fine-tuning.
- `/exports/` — exports de usuario para borrado de cuenta.
- `/backups/` — pg_dump locales.

El control real contra commitear pesos sigue siendo `*.bin`,
`*.safetensors`, `*.gguf`, `*.pt`, `*.ckpt` (sin ancla, porque ahí sí
queremos atrapar cualquier path).

### Tailwind v4 es CSS-first

`apps/web/` usa Tailwind v4, que es CSS-first. **No agregar
`tailwind.config.ts`**. Los tokens viven en
`apps/web/src/app/globals.css` con `@theme`. Para que Tailwind escanee
los componentes de `packages/ui`, usar `@source` desde el CSS:

```css
@import "tailwindcss";
@source "../../../../packages/ui/src/**/*.{ts,tsx}";
@theme {
  --color-background: ...;
}
```

Si volvés a ver `tailwind.config.ts` en `apps/web/`, borralo.

### NativeWind sigue en Tailwind 3

`apps/mobile/package.json` declara `tailwindcss ^3.4`. **No upgrade
a Tailwind 4** hasta que NativeWind anuncie soporte oficial. Esto es
una asimetría temporal: web v4, mobile v3. Los tokens conceptuales
siguen siendo los mismos; lo que cambia es cómo Tailwind los procesa.

### Services sin framework

Archivos en `apps/backend/app/services/` reciben dependencias
**por argumento**, no las importan globalmente:

```python
# bien
async def consolidate_memory(session: AsyncSession, user_id: UUID) -> int:
    ...

# mal
from app.core.deps import SessionLocal
async def consolidate_memory(user_id: UUID) -> int:
    async with SessionLocal() as session:
        ...
```

Razón: los services se testean sin levantar FastAPI ni un engine real.
El test inyecta una `AsyncSession` de SQLite en memoria o un mock.

### Consolidación de memoria siempre async

Toda escritura de memoria (semántica, episódica, procedural) pasa
por Celery. Nunca en el path de respuesta al usuario:

```python
# bien
await respond_to_user(...)
celery_app.send_task("consolidate_memory", args=[user_id, session_id])

# mal
await semantic.add(user_id, content, ...)
await respond_to_user(...)
```

Razón: la consolidación puede tomar 1-3 segundos (extracción + dedup +
embedding). Bloquear la respuesta rompe la UX y, peor, si la
consolidación falla, falla la respuesta entera.

### Pydantic es fuente de verdad, Zod es mirror

`apps/backend/app/schemas/` con Pydantic v2 strict define los
contratos request/response. `packages/shared-schemas/` con Zod replica
**a mano** lo que el cliente necesita validar.

Si Pydantic y Zod divergen:

1. Gana Pydantic.
2. Corregir Zod en el **mismo PR** que cambia Pydantic.
3. El PR no se mergea con Pydantic actualizado y Zod stale.

TODO eventual: codegen Zod desde Pydantic (no es prioridad MVP).

### `app/core/security.py` está sin implementar

`create_access_token`, `verify_access_token`, `hash_password`,
`verify_password` están todas en `raise NotImplementedError`. Es
intencional: el módulo de auth se cierra en un PR enfocado con tests
de extremo a extremo.

**No las completes parcialmente.** Si necesitás auth para tu feature,
abrí un issue/discusión primero. Si ya hay PR de auth en curso,
basate en esa rama, no hagas un parche local.

### CI corre solo manual hasta que existan lockfiles

`.github/workflows/ci.yml` tiene trigger `workflow_dispatch:`
solamente. Los jobs `lint-and-test-js` y `lint-and-test-py` esperan
`pnpm-lock.yaml` y `apps/backend/uv.lock` respectivamente; mientras
no existan (regla #1 frena los installs), CI no tiene sentido.

Cuando se corra `pnpm install` y `uv sync` por primera vez:

1. Verificar que los lockfiles quedaron generados.
2. Hacer un commit que los agregue: `chore: agregar pnpm-lock.yaml
   y apps/backend/uv.lock iniciales`.
3. Editar `.github/workflows/ci.yml` y reemplazar el bloque `on:`
   por:

   ```yaml
   on:
     pull_request:
       branches: [main]
     push:
       branches: [main]
   ```

4. Commit: `ci: reactivar CI en push y pull_request ahora que
   existen los lockfiles`.

### El doctor script es la primera línea de defensa

`scripts/ynara-doctor.sh` valida en un solo comando todas las
reglas mecánicas (gitignore, secrets, Supabase frontend, APIs IA
externas, etc.). **Exit 0 antes de cualquier PR.**

Si agregás una regla nueva que sea automatizable, sumá un check al
doctor en vez de dejarla solo en docs. El doctor es la verdad
ejecutable; las docs son la verdad declarativa. Ambas tienen que
estar alineadas.

## Cómo agregar reglas nuevas

PR contra este archivo con justificación. Si la regla es bloqueante,
considerar promoverla a `AGENTS.md`. Si la regla es automatizable,
agregar el check correspondiente a `scripts/ynara-doctor.sh` en el
mismo PR.
