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

## Cómo agregar reglas nuevas

PR contra este archivo con justificación. Si la regla es bloqueante,
considerar promoverla a `AGENTS.md`.
