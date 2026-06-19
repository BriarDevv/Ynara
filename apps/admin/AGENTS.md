# apps/admin/AGENTS.md — Reglas y mapa del panel interno

> Fuente canónica del repo: [`../../AGENTS.md`](../../AGENTS.md) (10 reglas no
> negociables). Este archivo es el **contrato + mapa operativo** del panel de
> administración: si vas a tocar `apps/admin`, leelo entero antes de editar.
> Decisión arquitectónica que lo habilita: [ADR-017](../../docs/architecture/adrs/ADR-017-admin-app-observabilidad-control-plane.md).

---

## 0. Qué es `apps/admin` (y qué NO es)

`apps/admin` es el **panel interno del equipo** (operadores técnicos y
founders): un *control plane* de observabilidad para **ver y operar** Ynara —
cuántos usuarios hay, qué modos se usan, si el moat (la memoria) está sano, qué
pasó en el `audit_log`, si el guard anti-prod está activo y si el serving LLM
responde. Es Next.js 16 + TS strict + Tailwind v4 (CSS-first) + TanStack Query
+ Zustand, **consistente 1:1 con [`apps/web`](../web/)** en stack, tokens y
primitivos.

**NO es la app del usuario final.** No hay chat, no hay memoria personal, no hay
contenido del usuario. Es un dashboard de **métricas agregadas cross-tenant** y
de **runtime/config**, detrás de un nuevo eje de autorización (`is_admin`). Todo
lo que muestra es agregación (`COUNT`/`GROUP BY`) o estado de infra — **nunca**
contenido descifrado de memoria ni PII.

---

## 1. Gates bloqueantes — parar y pedir humano

| Gate | Qué lo dispara | Qué hacer |
|---|---|---|
| **Perímetro de datos** (regla #2/#4) | Cualquier intento de exponer en una pantalla, schema, fixture o request: `record_hash`, `target_id`, contenido/`summary` descifrado de memoria, mensajes, emails u otra PII | **Prohibido.** El panel muestra solo agregados y metadata exponible. El `record_hash` y `target_id` se omiten en el **Zod schema** (no solo en el render). Si un endpoint nuevo los devuelve, no los parsees ni los pintes. |
| **Cliente Supabase** (regla #5) | `import "@supabase/supabase-js"` en cualquier archivo de este app | **Prohibido.** Todo dato pasa por la API de FastAPI (`/v1/admin/*`). Sin Supabase Auth/Storage/Realtime/RLS. |
| **IA externa** (regla #4) | `openai`, `anthropic`, `@google/generative-ai` desde este app | **Prohibido.** La inferencia es on-prem en el backend; el panel solo lee su salud. |
| **Tablas sagradas** (regla #3) | El panel consume vistas derivadas de `semantic_memory`/`episodic_memory`/`procedural_memory`/`audit_log` | El front es **read-only** sobre agregados: nunca escribe, nunca descifra, nunca expone hash. Los endpoints `/v1/admin/*` hacen COUNT/GROUP BY sin tocar las columnas sensibles. Cualquier cambio del **backend** sobre esas tablas sigue el gate de la regla #3 (tests + 1 aprobación humana). |
| **Instalación / commit** (regla #1) | `pnpm add`/`pnpm install`, `git commit`/`push` | Confirmación humana explícita. En esta app **no se corre gate**: solo se escriben archivos. |
| **Secrets** (regla #2) | `.env`, tokens, JWT admin | Nunca leer, copiar ni commitear. El token admin vive en `stores/admin.ts` (Zustand persist), nunca hardcodeado. |

---

## 2. Reglas duras heredadas (del contrato global)

1. **Soberanía del dato (regla #4).** El panel **nunca** saca dato del
   perímetro ni expone contenido del usuario. Solo agregados y metadata.
2. **Sin cliente Supabase (regla #5).** Todo va por FastAPI. Prohibido
   `@supabase/supabase-js`.
3. **Sin IA externa (regla #4).** Nada de `openai`/`anthropic`/`@google/*`.
4. **Read-only sobre tablas sagradas (regla #3).** Cero escritura, cero
   descifrado, cero `record_hash`/`target_id`/PII en la superficie.
5. **TypeScript strict.** Sin `any`, sin `// @ts-ignore` salvo justificación.
6. **Cero color hardcodeado.** Todo via tokens `var(--...)` de `globals.css`
   (paridad de marca con web). El gradiente vive SOLO en los 3 portadores
   (§5). Lo verifica `gradient-guard.test.ts`.
7. **`tabular-nums` en todo número.** Métricas, charts, conteos, latencias,
   paginación. Lo verifica `tabular-nums-guard.test.ts`.
8. **Honestidad de dato.** Los proxies se rotulan en la UI (DAU/WAU por
   sesiones, conversión por ratio, duración solo de sesiones cerradas). No
   inventar precisión que el schema no tiene.

---

## 3. Mapa del código (`src/`)

```
src/
├── app/
│   ├── layout.tsx              # RootLayout: <html> dark-first, fonts, script pre-paint, <Providers>
│   ├── providers.tsx           # QueryClientProvider + ThemeApplier + A11yApplier (+ MSW gate en dev)
│   ├── globals.css             # tokens de marca (clon web) + z-index/heatmap admin-específicos
│   ├── fonts.ts / a11y-init.ts # clones de web (Space Grotesk + DM Sans; anti-FOUC)
│   └── (panel)/                # shell + las 6 pantallas (Overview, Usuarios, Modos, Moat, Audit, Sistema)
├── components/
│   ├── shell/                  # AdminShell, Sidebar, Topbar, RangeSelector, ThemeToggle, PerimeterBadge, ApiStatusFooter
│   ├── ui/                     # primitivos PORTADOS de apps/web/src/components/ui (copia 1:1, color plano por token)
│   └── charts/                 # data-viz por token, CERO gradiente (Sparkline, AreaTimeSeries, ModeDonut, UsageHeatmap, …)
├── features/                   # un dir por pantalla: overview/ users/ modes/ moat/ audit/ system/
│   └── <feature>/              # components/ + hooks/use<Feature>.ts + schemas.ts (Zod del endpoint)
├── lib/
│   ├── api.ts                  # configureApi(@ynara/core) con baseUrl + token admin
│   ├── queryKeys.ts            # qk.admin.* (factory local, mismo patrón que @ynara/core/query-keys)
│   ├── env.ts / cn.ts / clientStorage.ts / time.ts / relativeTime.ts / viewTransition.ts  # clones web
│   └── mocks-browser.ts        # arranque MSW client-side (dev)
├── stores/                     # admin (token JWT), theme (default theme-dark), a11y, range (24h/7d/30d/90d)
├── config/site.ts             # siteConfig admin
├── styles/motion.css          # clon idéntico de apps/web (keyframes + utilities .anim-*)
├── fixtures/                   # datos deterministas para dev sin backend + handlers MSW por /v1/admin/*
└── __tests__/                 # gradient-guard, tabular-nums-guard, admin-schemas (parse de fixtures)
```

**Consistencia con web.** Cuando algo es "clon de web" (primitivos `ui/`,
`motion.css`, `fonts`, `cn`, `clientStorage`, `env`), se copia el archivo **real**
de `apps/web` y se adapta solo lo mínimo. No inventar APIs nuevas. Los iconos
salen del registry de `@ynara/ui` (no SVGs sueltos). Los primitivos UI se
**portan** desde `apps/web/src/components/ui` (no viven en `@ynara/ui` todavía).

---

## 4. Playbooks — cómo agregar X

**Agregar una pantalla.** Ruta en `app/(panel)/<ruta>/page.tsx` (kebab-case) →
entrada en `components/shell/nav-items.ts` (con `IconName` del registry) →
feature en `features/<feature>/` con `components/`, `hooks/use<Feature>.ts`,
`schemas.ts` → fixture en `fixtures/<feature>.ts` + handler en
`fixtures/handlers.ts` → documentar en [`docs/SCREENS.md`](./docs/SCREENS.md) y
[`docs/DATA-CONTRACTS.md`](./docs/DATA-CONTRACTS.md).

**Agregar un hook de datos.** `features/<feature>/hooks/use<Feature>.ts`:
`useQuery({ queryKey: qk.admin.<vista>(range), queryFn: async () =>
Schema.parse(await api.get<unknown>("/v1/admin/<vista>?range=...")) })`. El
`Schema.parse` es el gate de privacidad: el Zod **omite** `record_hash`/`target_id`
y todo lo no exponible. La mayoría de las vistas se segmentan por `range`;
`system` no (es runtime/config).

**Agregar un componente.** Si es primitivo de marca → portar 1:1 de
`apps/web/src/components/ui` a `components/ui/`. Si es de feature →
`features/<feature>/components/`. Color **plano** por token (`var(--...)`),
`tabular-nums` en cualquier número, motion via clases `.anim-*` de `motion.css`.
Documentar en [`docs/COMPONENTS.md`](./docs/COMPONENTS.md).

**Agregar un chart.** `components/charts/`. Color por token (tints/fills de modo,
escala `--heat-*`, `--layer-*`). **CERO gradiente** (lo bloquea el
gradient-guard). `tabular-nums` en ejes/valores/tooltips (lo exige el
tabular-nums-guard). Si un chart legítimamente no pinta dígitos, marcar
`// tabular-nums-guard: n/a` con el motivo.

**Conectar a un endpoint real.** Schema Zod en `features/<feature>/schemas.ts`
mirror del Pydantic del backend → hook con `Schema.parse` → si el shape valida
los fixtures, el wire al backend real no cambia el front. Endpoints en
[`docs/DATA-CONTRACTS.md`](./docs/DATA-CONTRACTS.md).

---

## 5. Convenciones

- **Dark-first.** `theme.ts` arranca en `theme-dark` (herramienta de uso
  prolongado). Toggle a marfil disponible. Re-declarar tokens en
  `html.theme-dark`, nunca un segundo `@theme`.
- **Tokens, cero hex.** Todo color via `var(--...)`. Sistema clonado de web +
  extensiones admin (z-index tokenizado `--z-*`, escala heatmap `--heat-*`,
  alias de capa `--layer-*`).
- **Gradiente restringido a 3 portadores.** Solo `LivingField.tsx`,
  `YnaraMark.tsx` y `YnaraOrb.tsx` pueden usar `linear/radial/conic-gradient`.
  Cualquier otro lado = anti-patrón. `src/__tests__/gradient-guard.test.ts` lo
  bloquea en CI.
- **`tabular-nums` obligatorio.** En toda métrica, valor de chart, conteo,
  latencia y paginación. `src/__tests__/tabular-nums-guard.test.ts` lo bloquea.
- **Motion CSS puro.** Keyframes + utilities `.anim-*` de `styles/motion.css`
  (clon de web) + View Transitions API. Sin GSAP/Lenis/framer. Animar SOLO
  `transform`/`opacity`. Respetar `prefers-reduced-motion` y `html.motion-off`.
- **Server components por defecto.** `"use client"` solo donde hace falta
  (hooks de cliente, eventos, stores).
- **TanStack Query v5** para data; **Zustand v5** para estado global mínimo
  (token admin, theme, a11y, range). Sin `useEffect + fetch`.
- **Naming.** Rutas kebab-case; componentes `PascalCase.tsx`; hooks
  `useNombre.ts`.
- **Commits.** Conventional Commits en español, scope `admin`
  (`feat(admin): …`), imperativo o noun-phrase, atómicos (reglas #6/#7/#8).

---

## 6. Tests

- **Vitest** (`vitest run`) + Testing Library (jsdom). Config en
  `vitest.config.ts` (alias `@/` + workspace packages resueltos a TS source).
- Guards de diseño que corren en cada PR: `gradient-guard.test.ts` (cero
  gradiente fuera de los 3 portadores) y `tabular-nums-guard.test.ts` (todo
  número en charts/features usa `tabular-nums`).
- `admin-schemas.test.ts` parsea todos los fixtures con sus Zod → garantiza que
  los fixtures cumplen el contrato (y que el contrato no expone PII).
- E2E con Playwright vive en `tests/e2e/` del root del monorepo (smoke de las 6
  rutas contra backend con admin sembrado).

---

## 7. Docs del panel

| Doc | Para qué |
|---|---|
| [`docs/SCREENS.md`](./docs/SCREENS.md) | Las 6 pantallas + qué datos muestra cada una. |
| [`docs/COMPONENTS.md`](./docs/COMPONENTS.md) | Inventario de componentes (shell, ui, charts, features). |
| [`docs/DATA-CONTRACTS.md`](./docs/DATA-CONTRACTS.md) | Endpoints `/v1/admin/*` + Zod + nota de privacidad. |
| [`README.md`](./README.md) | Quickstart humano (qué es, dev con mocks, scripts). |

**Regla de los catálogos** (igual que el backend): si agregás una pantalla,
componente, chart o contrato, **actualizás el doc correspondiente en el mismo
PR**.

ADRs relevantes:
[ADR-017](../../docs/architecture/adrs/ADR-017-admin-app-observabilidad-control-plane.md)
(esta app: observabilidad + control plane + eje de autorización `is_admin`),
[ADR-005](../../docs/architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md)
(Supabase solo Postgres),
[ADR-016](../../docs/architecture/adrs/ADR-016-mobile-codigo-compartido-packages-core.md)
(`@ynara/core` comparte cliente HTTP + stores + query keys).
