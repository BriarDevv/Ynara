# apps/admin — Panel interno de Ynara

Next.js 16 (App Router) + TypeScript strict + Tailwind v4 (CSS-first) +
TanStack Query v5 + Zustand v5.

Es el **control plane interno del equipo** (operadores y founders): observar y
operar Ynara. No es la app del usuario final — acá no hay chat ni memoria
personal, solo métricas agregadas y estado de infra.

> Decisión que lo habilita: [ADR-017](../../docs/architecture/adrs/ADR-017-admin-app-observabilidad-control-plane.md).

## Antes de tocar nada

1. [`../../AGENTS.md`](../../AGENTS.md) — las 10 reglas no negociables.
2. [`./AGENTS.md`](./AGENTS.md) — reglas + mapa de este app.
3. [`docs/`](./docs/) — pantallas, componentes y contratos de API.

## Qué muestra

Seis pantallas, todas sobre datos **agregados** (nunca contenido del usuario):

1. **Overview** (`/`) — perímetro, KPIs, sesiones/día, mix de modos, preview de audit.
2. **Usuarios** (`/usuarios`) — DAU/WAU/MAU (proxy por sesiones), heatmap, conversión, signups.
3. **Modos** (`/modos`) — mix de los 5 modos, duración media por modo.
4. **Salud del Moat** (`/moat`) — memoria por capa (semántica/episódica/procedural), procedural health, backlog de consolidación.
5. **Audit Log** (`/audit`) — vista soberana del `audit_log`: filtrable, **sin** `record_hash` ni contenido descifrado.
6. **System Health** (`/sistema`) — DB/Redis, guard anti-prod, inventario de runtime.

## Levantar en dev (con mocks)

El panel arranca **100% sobre fixtures** vía MSW — no necesita backend para
desarrollar la UI.

```sh
cp .env.example .env.local          # NEXT_PUBLIC_ENABLE_MOCKS=true ya viene activo
pnpm install                        # desde el root del monorepo (gate: confirmación humana)
pnpm --filter @ynara/admin dev      # dev server (Next) con MSW sirviendo /v1/admin/*
```

Para apuntar al backend real: poner `NEXT_PUBLIC_ENABLE_MOCKS=false` y
`NEXT_PUBLIC_API_URL` al FastAPI, y proveer un JWT de admin (regla #1: el
backend gatea con `require_admin`).

## Scripts

```sh
pnpm dev            # dev server :3000 (predev corre msw init)
pnpm build          # build de producción
pnpm start          # serve del build
pnpm lint           # biome check (desde root)
pnpm typecheck      # tsc --noEmit
pnpm test           # vitest run (incluye gradient-guard + tabular-nums-guard)
pnpm test:watch     # vitest en watch
```

## Estructura

```
src/
├── app/          # App Router: layout, providers, globals.css, (panel)/ con las 6 pantallas
├── components/   # shell/ (sidebar, topbar, badge) · ui/ (primitivos portados de web) · charts/
├── features/     # un dir por pantalla: components/ + hooks/ + schemas.ts (Zod)
├── lib/          # api, queryKeys, env, cn, time, mocks-browser
├── stores/       # admin (token), theme (dark-first), a11y, range (24h/7d/30d/90d)
├── config/       # site.ts
├── styles/       # motion.css (clon de web)
├── fixtures/     # datos deterministas + handlers MSW
└── __tests__/    # guards de diseño + parse de fixtures
```

## Reglas de oro (resumen — detalle en AGENTS.md)

- **Cero PII / cero contenido descifrado / cero `record_hash`.** Solo agregados.
- **Cero color hardcodeado**: todo via tokens `var(--...)`. Gradiente solo en 3
  portadores (LivingField, YnaraMark, YnaraOrb) — lo bloquea el gradient-guard.
- **`tabular-nums` en todo número** — lo bloquea el tabular-nums-guard.
- **Sin Supabase JS, sin IA externa, TS strict.**
- **Consistencia 1:1 con `apps/web`**: lo "clon de web" se copia del archivo
  real, no se reinventa.

## Variables de entorno

Copiar `.env.example` a `.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8080
NEXT_PUBLIC_ENABLE_MOCKS=true
NEXT_PUBLIC_POSTHOG_KEY=
NEXT_PUBLIC_SENTRY_DSN=
```
