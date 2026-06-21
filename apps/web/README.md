# apps/web — Frontend web de Ynara

Next.js 16 (App Router) + TypeScript strict + Tailwind v4 + shadcn/ui.

## Antes de tocar nada

Leer:
1. [`../../AGENTS.md`](../../AGENTS.md) — reglas no negociables.
2. [`./AGENTS.md`](./AGENTS.md) — reglas específicas de este app.
3. [`../../DESIGN.md`](../../DESIGN.md) — sistema visual (vacío
   hasta aprobación: usar tokens genéricos de Tailwind).

## Estructura

```
src/
├── app/         # App Router (rutas, layouts, páginas)
├── components/  # Componentes reutilizables (UI + presentational)
├── features/    # Features por dominio (chat, memoria, settings...)
├── lib/         # Utilidades, clients HTTP, helpers
├── config/      # Configuración estática del site
├── styles/      # CSS extras si no entran en globals.css
└── types/       # Types compartidos del frontend
```

## Stack

- Next.js 16 (App Router)
- TypeScript strict
- Tailwind CSS v4 (CSS-first config)
- shadcn/ui (componentes base, copy-paste)
- GSAP + Lenis (animación + smooth scroll)
- TanStack Query v5 (data del cliente)
- Zustand v5 (estado global mínimo)
- React Hook Form + Zod (formularios + validación)
- Auth.js v5 (sesión)

## Scripts

```sh
pnpm dev            # dev server :3000
pnpm build          # build de producción
pnpm start          # serve del build
pnpm test           # tests
pnpm typecheck      # tsc --noEmit
```

## Variables de entorno

Copiar `.env.example` a `.env.local` y completar.

### Mocks (MSW) y dev contra el backend real

`NEXT_PUBLIC_ENABLE_MOCKS` es **flag-driven con default ON** (mismo patrón que
`apps/admin`). Sin `.env.local`, `pnpm dev` levanta con MSW sirviendo los
endpoints fake (offline-first). Para apuntar al backend real:

```sh
# apps/web/.env.local
NEXT_PUBLIC_ENABLE_MOCKS=false
NEXT_PUBLIC_API_URL=http://localhost:8080
```

En `production` los mocks están **siempre off** sin importar el flag
(hard-gate por `NODE_ENV`).

> **Regla #5**: prohibido usar `@supabase/supabase-js` desde acá.
> Todo dato pasa por la API de FastAPI.
