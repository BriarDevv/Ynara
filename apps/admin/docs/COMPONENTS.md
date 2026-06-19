# COMPONENTS.md — Inventario de componentes

Catálogo de los componentes de `apps/admin`, agrupados por capa. Reglas
transversales: color **plano** por token (`var(--...)`), `tabular-nums` en todo
número, motion via clases `.anim-*` de `styles/motion.css`, gradiente **solo** en
los 3 portadores (`LivingField`, `YnaraMark`, `YnaraOrb`).

> Si agregás un componente, sumalo acá en el mismo PR.

---

## `components/shell/` — chrome del panel

| Componente | Responsabilidad |
|---|---|
| `AdminShell` | Grid raíz `248px 1fr` (rail 64px en < lg). Monta Sidebar + Topbar + `LivingField` de fondo + `<main>` con `max-w` editorial. |
| `Sidebar` | Nav agrupada (3 grupos con separadores caption). Item activo = barra de acento izquierda + `bg-bg-soft`. Lee `usePathname()`. |
| `Topbar` | Glass sticky `z-topbar`. Wordmark + breadcrumb + `PerimeterBadge compact` + `RangeSelector` + `ThemeToggle` + `AdminMenu`. |
| `nav-items.ts` | IA de navegación (data): grupos Overview / Producto / El Moat / Soberanía, con `IconName` del registry de `@ynara/ui`. |
| `RangeSelector` | Segmented control `24h·7d·30d·90d` → `useRangeStore`. |
| `ThemeToggle` | Toggle Noche/marfil → `useThemeStore` (default `theme-dark`). |
| `AdminMenu` | Identidad admin (Diamond + `display_name`) como disclosure → popover con "Cerrar sesión" (`useLogout`). Cierre por click afuera + Escape. |
| `AuthGuard` | Guard del grupo `(panel)`: rebota a `/login` si no hay token (post-mount, SSR-safe). Ver [`AUTH.md`](./AUTH.md). |
| `PerimeterBadge` | **Firma de soberanía.** `Diamond` + label. Estados `intact`/`attention`/`verifying`. Variantes `compact`/`hero`. Tooltip explica el perímetro. **Nunca gradiente.** |
| `ApiStatusFooter` | Dot de estado + "API" + latencia (`tabular-nums`) + build version. |

## `components/ui/` — primitivos portados de `apps/web`

Copia **1:1** de `apps/web/src/components/ui/` (web-only, DOM + Tailwind por
token). Mantienen el patrón `BASE` + `VARIANTS: Record<Variant,string>` + tokens
arbitrarios `[var(--token)]`. Importan de `@/lib/cn`.

`Button`, `Card`, `OptionCard`, `ChipGroup`, `ModeChip`, `Diamond`,
`ProgressDots`, `EmptyStateCard`, `Toast`, `Sheet`, `SuggestionCard`,
`YnaraMark`, `YnaraWordmark`, `YnaraOrb`, `LivingField`, `modes.ts`.

> Se portan a demanda: `TextField`/`Textarea`/`Toggle` solo si una pantalla los
> pide (p.ej. búsqueda en audit). No portar lo que no se usa. El único form del
> panel (login) usa un `Field` inline (input + label + error, `forwardRef`) en
> `app/login/page.tsx`; cuando aparezca un segundo form, portar el `TextField`
> de web a `components/ui/`.

## `components/charts/` — data-viz por token (cero gradiente)

| Chart | Qué dibuja |
|---|---|
| `Sparkline` | Path SVG fino `--color-azul`, sin ejes ni relleno. |
| `AreaTimeSeries` | Serie temporal única (sesiones/día). Línea + área plana 0.12 (sin gradiente). |
| `LineMultiSeries` | 3 líneas planas de capa (`--layer-semantic/episodic/procedural`). |
| `ModeBarChart` | Barras horizontales por modo, fill plano `mode.fillVar`. |
| `ModeDonut` | Donut mix de modos, slices `mode.fillVar`, centro con total. |
| `UsageHeatmap` | Grid 53×7, 5 niveles de opacidad de azul (`--heat-1..5`) sobre `--heat-0`. |
| `ConfidenceHistogram` | Buckets de `confidence` en barras azules; `stale` en `--color-error`. |
| `chart-utils.ts` | Escalas, ticks, path builders. **Sin color hardcodeado.** |

Todos los charts: ejes/valores/tooltips con `tabular-nums`. Un chart puramente
geométrico que no pinte dígitos puede marcar `// tabular-nums-guard: n/a`.

## `features/<feature>/components/` — componentes de pantalla

| Feature | Componentes |
|---|---|
| `overview/` | `StatusHero`, `KpiStrip`, `KpiCard`, `AuditPreview` |
| `users/` | `ActivityKpis`, `ConversionFunnel`, `SignupsTable` |
| `modes/` | `ModeMix`, `ModeDuration`, `ModeCardStrip` |
| `moat/` | `MoatHealthHero`, `MoatTower`, `LayerGrowth`, `ProceduralHealth`, `ConsolidationHeartbeat` |
| `audit/` | `AuditFilters`, `AuditTable`, `AuditRow` |
| `system/` | `ProdGuardBanner`, `StatusCard`, `RuntimeInventory` |
| `auth/` | (sin componentes; `hooks/useLogin.ts` + `hooks/useLogout.ts` + `schemas.ts`). UI en `app/login/page.tsx`. Ver [`AUTH.md`](./AUTH.md). |

Cada feature también tiene `hooks/use<Feature>.ts` (TanStack Query + `Schema.parse`)
y `schemas.ts` (Zod del endpoint). Detalle de props en el blueprint; contrato de
datos en [`DATA-CONTRACTS.md`](./DATA-CONTRACTS.md).

## Hooks de UI

| Hook | Para qué |
|---|---|
| `useCountUp` | Count-up 0→valor en rAF para los números grandes (solo primer load del rango). Se neutraliza bajo `prefers-reduced-motion`/`html.motion-off`. |
