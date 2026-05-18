# apps/web/AGENTS.md — Reglas del frontend web

> Fuente canónica del repo: [`../../AGENTS.md`](../../AGENTS.md).
> Acá solo reglas específicas del frontend web.

## Reglas duras

1. **Sin cliente Supabase** (regla #5 del contrato global).
   Prohibido `import "@supabase/supabase-js"` en cualquier archivo
   de este app. Todo va por la API de FastAPI.
2. **Sin llamadas directas a APIs de IA externa** (regla #4).
   Prohibido `openai`, `anthropic`, `@google/generative-ai` desde
   este app. La inferencia está en el backend.
3. **TypeScript strict.** Sin `any`. Sin `// @ts-ignore` salvo
   justificación.
4. **No hardcodear colores ni tipografías.** Tokens vía CSS variables
   en `globals.css`, consumidos por Tailwind v4 `@theme`. Sistema visual
   completo documentado en [`../../DESIGN.md`](../../DESIGN.md).

## Patrones recomendados

- **Server components por defecto.** Marcar `"use client"` solo
  cuando hace falta (eventos, hooks de cliente).
- **TanStack Query v5** para data de cliente. Nada de `useEffect +
  fetch` para fetching.
- **Zustand** solo para estado verdaderamente global (no por feature).
  Cada feature tiene su propio store si lo necesita; sin singleton
  monstruo.
- **React Hook Form + Zod** para formularios. Schemas Zod
  compartidos vienen de `@ynara/shared-schemas`.
- **GSAP + Lenis** para animaciones; respetar
  `prefers-reduced-motion`.

## Cliente HTTP

`src/lib/api.ts` (TODO crear) tiene un fetcher tipado que apunta al
backend. Usar **ese** cliente, no `fetch` crudo regado por la app.

## Naming

- Rutas Next.js: `kebab-case` (`/modo-bienestar`, no `/modoBienestar`).
- Componentes: `PascalCase.tsx` si son principales (`ChatPanel.tsx`),
  `kebab-case.tsx` para utilidades.
- Hooks: `useNombre.ts`.

## Dónde viven las primitives

- **`apps/web/src/components/ui/`** → primitives web-only (Button, Card,
  TextField, OptionCard, YnaraMark, etc.). Pueden usar APIs DOM y
  Tailwind sin restricciones.
- **`apps/web/src/components/`** (raíz) → composiciones no-feature
  (header global, footer, etc.).
- **`apps/web/src/features/<feature>/`** → todo lo de un feature
  (steps, hooks, store, schemas, tests, componentes propios).
- **`packages/ui/`** → reservado para cosas **realmente** web/mobile
  compartibles y RN-compatibles. Por ahora vacío. No mover primitives
  acá hasta que haya consumidor mobile.

## Sandbox del design system

`/test-ds` ([`src/app/test-ds/page.tsx`](src/app/test-ds/page.tsx))
renderiza el sistema visual entero (paleta, tipografía, gradientes,
modos, botones, cards). Después de cada cambio a `globals.css` o
primitives, abrir `/test-ds` y verificar a ojo antes del PR.

## Tests

- Vitest o Jest (TODO decidir y reflejar en `package.json`).
- E2E con Playwright (vive en `tests/e2e/` en el root del monorepo).
