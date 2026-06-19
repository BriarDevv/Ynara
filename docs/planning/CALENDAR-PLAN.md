# Plan de ejecución: Calendario / Agenda

> Plan incremental para llevar la Agenda de su estado actual (mock-first, sin
> recurrencia/timezone/solapamientos) a un calendario sólido con paridad web +
> mobile. **Fundamento:** [`CALENDAR-RESEARCH-2026.md`](./CALENDAR-RESEARCH-2026.md)
> (veredicto **build-render / buy-logic-headless**, ya verificado).
> Generado: 2026-06-19.

---

## Estado actual (anclado al código)

- **Schema** [`packages/shared-schemas/src/agenda.ts`](../../packages/shared-schemas/src/agenda.ts):
  `AgendaEvent { id, title, start_at (ISO+offset), duration_min, mode, status, location }`.
  El fin se deriva. **Falta:** `time_zone`, `all_day`, `recurrence`, multi-día.
- **Hooks compartidos** [`packages/core/src/features/agenda/api.ts`](../../packages/core/src/features/agenda/api.ts):
  `useEvents/useCreate/usePatch/useDelete` ya en core, mock-backed contra `/v1/events`.
  CRUD tipado listo; backend no existe aún.
- **Helpers puros** [`apps/web/src/features/agenda/format.ts`](../../apps/web/src/features/agenda/format.ts):
  **web-only** (mobile tiene los suyos). El algoritmo de layout debe vivir en core.
- **DayView**: ventana fija **8–20h** (clipea), bloques `absolute inset-x-1` →
  **bug de solapamiento**, sin resumen sr-only a11y.
- **WeekView**: ya tiene auto-fit de horas + resumen sr-only accesible; **tampoco**
  tiene columnas (solapados del mismo día se pisan).

## Principios (del research)

1. **BUILD el render, BUY la lógica headless.** Ninguna lib de calendario DOM
   (no se comparte con RN, pisa el design system).
2. **Lógica pura en `@ynara/core`** (layout, tiempo, recurrencia) — web y mobile
   la consumen; el render es por plataforma.
3. **a11y:** time-grid con solapados ≠ `role=grid` → lista semántica de `<button>`
   + resumen sr-only. `role=grid` solo en Mes con modelo de teclado completo.
4. **No virtualizar el time-grid** (acotado); sí listas largas y capear el Mes.

---

## Fases (cada una = 1 PR atómico)

### Fase 0 — ADR-018: congelar `CalendarEvent`  ·  *doc-only*
[`docs/architecture/adrs/ADR-018-*`](../architecture/adrs/). Decide el modelo
(`time_zone` IANA, `all_day`, `recurrence` RRULE/RDATE/EXDATE + `recurrence_id`/
`original_start` para overrides, multi-día), el engine (`rrule-temporal` +
`@js-temporal/polyfill` detrás de una interfaz `expand(event, range)`), y el
contrato `/v1/events?from&to` (instancias expandidas). **No toca código** — es el
gate que habilita las Fases 4–5.

### Fase 1 — Quick-win: algoritmo de columnas  ·  *front, sin backend*
Arregla el bug visible. **Pure + test en core**, render web lo consume.
- `@ynara/core/features/agenda/layout.ts`: `layoutColumns(intervals) → Map<id,{col,cols}>`
  (clusters de solapamiento transitivo + asignación greedy de columnas, §1.4 del research).
- Web `DayView`/`WeekView`: `left = col/cols`, `width = 1/cols` (en vez de ancho completo).
- a11y: sumar resumen sr-only a `DayView` (como ya tiene `WeekView`) + grilla `aria-hidden`.
- **Acepta cuando:** dos eventos a la misma hora quedan lado a lado; core test verde;
  web tsc+vitest+build verdes.

### Fase 2 — Grilla completa  ·  *front*
`DayView`: auto-fit 24h (como `WeekView` ya hace con `hourBounds`), **scroll-to-now**
al montar **sin robar foco**, franja **all-day** arriba del time-grid, multi-día.
*(All-day/multi-día "de verdad" dependen del modelo — Fase 4; la grilla 24h +
scroll-to-now se hace ya, solo presentación.)*

### Fase 3 — Interacción  ·  *front*
Puras en core (worklet-safe, §5.B del research): `pxToMinutes`, `snapTo(15)`,
`hitTest`, `clampToDay`, `deriveTimes(delta)`. Web: pointer-events → tap-para-editar
(sheet con `usePatchEvent`/`useDeleteEvent`, que ya existen), drag-crear/mover/resize.
Mobile reusa las puras con `gesture-handler` + Reanimated (su lane).

### Fase 4 — Modelo + recurrencia en core  ·  *gate regla #1 (deps)*
`AgendaEventSchema` → campos nuevos **opcionales** (back-compat). `expand(event, range)`
con `rrule-temporal` detrás de la interfaz. **Spike Hermes/RN temprano** (su soporte RN
no está documentado). Deps nuevas (`rrule-temporal`, `@js-temporal/polyfill`) → aprobación.

### Fase 5 — Backend  ·  *gate aprobación humana (reglas #1/#3)*
`CalendarEvent` model + migración Alembic + `/v1/events` con expansión de instancias
y overrides ("este" / "este y siguientes" / "serie"). Toca `apps/backend` → **1 aprobación
humana explícita en el PR**. No se arranca sin OK.

### Fase 6 — Vista Mes  ·  *front, al final*
`MonthView` nuevo: grilla de celdas 6×7 (6 semanas fijas) + "+N more" → componente
**aparte**, no parametrizar el time-grid. a11y: tabla semántica, o `role=grid` solo si
se implementa el modelo de teclado completo (APG date-picker).

---

## Orden y dependencias

```
Fase 0 (ADR) ──────────────┐ desbloquea
Fase 1 → Fase 2 → Fase 3   │
Fase 6 (independiente)     │
                           └─→ Fase 4 → Fase 5
```

Las Fases 1–3 y 6 son **front, sin backend** → se mergean apenas pasan los gates.
El ADR (Fase 0) **solo desbloquea 4–5**; el quick-win **no** lo espera.

## Gates por PR (no negociables, AGENTS.md)

`pnpm exec biome check --write <paths>` · `pnpm --filter @ynara/core typecheck` +
`vitest run` (si toca core) · `pnpm --filter ./apps/web exec tsc --noEmit` +
`vitest run` + `build` (si toca web). Commits chicos y atómicos; sin push/merge a
`main` sin OK humano (todo por PR mergeado en GitHub).
