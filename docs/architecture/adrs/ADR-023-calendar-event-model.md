# ADR-023: Modelo de evento de calendario (recurrencia, timezone, all-day, multi-día)

## Estado
Propuesto

## Fecha
2026-06-19

## Contexto

El dominio **Agenda** se construyó mock-first (build-plan Fase F). El contrato
actual [`packages/shared-schemas/src/agenda.ts`](../../../packages/shared-schemas/src/agenda.ts)
es:

```
AgendaEvent { id, title, start_at (ISO+offset), duration_min, mode, status, location }
```

con el fin derivado (`start_at + duration_min`). Es suficiente para pintar
bloques sueltos en un día/semana, pero le faltan las cuatro cosas que definen
un calendario de verdad, hoy todas ausentes:

1. **Zona horaria real.** Todo se renderiza con `new Date().getHours()` (hora
   local del dispositivo). Un evento creado en Buenos Aires se ve corrido si lo
   abrís en otro huso, y no hay forma de fijar "9:00 *allá*".
2. **Recurrencia.** No hay forma de expresar "todos los lunes". Cada repetición
   sería una fila duplicada.
3. **All-day.** No se puede modelar un evento de día completo (cumpleaños,
   feriado) — `duration_min` obliga a una hora de inicio.
4. **Multi-día.** Un evento que cruza medianoche o dura días no tiene
   representación clara.

El [research verificado](../../planning/CALENDAR-RESEARCH-2026.md) ya decidió el
**veredicto** (build-render / buy-logic-headless) y el **estándar** (iCalendar /
RFC 5545, como Google/Apple/Outlook). Lo que falta y amerita ADR es **congelar
la forma del modelo** antes de:

- tocar `apps/backend` (crear el modelo `CalendarEvent` + migración Alembic +
  `/v1/events`) — regla #1/#3 de `AGENTS.md`;
- sumar dependencias nuevas (`rrule-temporal`, `@js-temporal/polyfill`) — regla #1.

Es un cambio de contrato que sobrevive a la etapa y que web + mobile + backend
comparten, por eso va por ADR (AGENTS regla #6, CONTRIBUTING "cambios
arquitectónicos").

## Decisión

Adoptar el modelo canónico de iCalendar/RFC 5545 (el que exponen Google
Calendar API y Microsoft Graph), aterrizado a nuestro stack.

### 1. Forma del evento

El **shape canónico** (mismo en TS y en el backend). En el frontend el tipo
sigue llamándose `AgendaEvent` (extendido, los campos nuevos **opcionales** para
back-compat con el mock actual y para no romper la web); en el backend el modelo
SQLAlchemy/Pydantic se llama **`CalendarEvent`** y la tabla `calendar_events`.
Mismos campos, se espejan ("Pydantic gana, Zod sigue").

Campos nuevos sobre el `AgendaEvent` actual:

| Campo | Tipo | Semántica |
|---|---|---|
| `time_zone` | `string` (IANA) \| null | Huso del wall-clock del evento (ej. `"America/Argentina/Buenos_Aires"`). Requerido para eventos con `recurrence`; default = huso del usuario. **No** se reemplaza `start_at` (sigue ISO+offset): el offset es el instante, `time_zone` es la regla para recurrencia/DST. |
| `all_day` | `boolean` | Si `true`, el evento es una **fecha sin hora**; `start_at` se interpreta como fecha (00:00 local) y la duración se cuenta en días. |
| `recurrence` | `string[]` \| null | Líneas RFC 5545: `RRULE`/`RDATE`/`EXDATE`. `null`/`[]` = evento único. |
| `recurrence_id` | `string` (ISO) \| null | En una instancia **override** ("solo este" de una serie): el inicio original que reemplaza. |
| `original_start` | `string` (ISO) \| null | Inicio original de la instancia override (para casarla con la serie madre). |

`duration_min` **se conserva** (es forma iCalendar legal — `DTSTART` + `DURATION`)
y sirve para multi-día (una duración > 1440 cruza días). El fin sigue derivado.
`mode`/`status`/`location` quedan igual.

### 2. Motor de lógica (headless, en `@ynara/core`)

- **Recurrencia:** `rrule-temporal` (MIT, RFC 5545 + 7529, construido sobre
  Temporal) detrás de una **interfaz fina en core**:
  `expand(event, { from, to }) → CalendarInstance[]`. La interfaz aísla el engine:
  si el soporte RN/Hermes no alcanza, se puede swapear por `rrule.js` (expandido en
  floating) + reproyección con Temporal sin tocar a los consumidores.
- **Tiempo/timezone:** `Temporal` (TC39 Stage 4, mar-2026) con
  `@js-temporal/polyfill` en RN/Hermes + Safari.
- Ambas son lógicas **puras y testeables** → viven en core, las consumen web y
  mobile. El render sigue siendo por plataforma.

### 3. Contrato del endpoint (habilita Fase 5, no se implementa acá)

- `GET /v1/events?from=&to=` devuelve **instancias ya expandidas** del rango
  `[from, to)` — no las series madre crudas. Cada instancia recurrente trae su
  `recurrence_id`/`original_start`.
- Edición con alcance: `PATCH`/`DELETE /v1/events/{id}?scope=this|following|all`
  ("solo este" = instancia override con `recurrence_id`; "este y los siguientes" =
  `UNTIL` en la RRULE vieja + serie nueva; "toda la serie" = editar la madre).

## Consecuencias positivas

- El modelo deja de ser un placeholder: soporta los cuatro casos que faltan sin
  otro cambio de contrato más adelante.
- Estándar real → interop futura (importar/exportar `.ics`, sync con Google/Apple)
  queda en el camino, no contra la corriente.
- La lógica difícil (recurrencia, DST) es headless, pura y compartida web/mobile;
  el render y el design system quedan intactos (veredicto del research).
- Campos opcionales = back-compat total con el mock y la web actuales; la
  migración del frontend es incremental.

## Consecuencias negativas

- `Temporal` necesita polyfill en RN/Hermes y Safari (peso + un punto de
  integración). `rrule-temporal` es chica y su soporte RN **no está documentado**
  → riesgo a despejar con un spike.
- Recurrencia + overrides + DST es lógica intrínsecamente compleja: más tests,
  más casos borde (eventos que "saltan" en el cambio de hora, EXDATE, etc.).
- El backend (Fase 5) debe expandir instancias server-side → no es un CRUD trivial.

## Mitigaciones

- **`expand()` detrás de interfaz** en core: el engine de recurrencia es un
  detalle reemplazable, no un acople. Spike de Hermes/RN **antes** de fijar la dep
  (regla #1) — si falla, plan B (`rrule.js` floating + Temporal) sin tocar consumidores.
- Campos **opcionales** + el contrato espejado (Zod/Pydantic) → el frontend migra
  sin esperar al backend (sigue mock-first hasta Fase 5).
- Suite de tests de la lógica pura (expansión, DST, overlap) como red de
  seguridad, mock-first, sin necesidad de backend.

## Alternativas descartadas

- **Guardar solo UTC, sin `time_zone`.** Alcanza para eventos sueltos pero
  **rompe la recurrencia** en cambios de DST (un "9:00 cada lunes" se corre 1h).
  Google **exige** `timeZone` IANA en eventos recurrentes. Descartada.
- **`dtend` explícito en vez de `duration_min`.** Equivalente; mantenemos
  `duration_min` por continuidad con `Task` y el mock (una sola fuente del fin).
- **Recurrencia "casera" (sin lib).** Reimplementar RFC 5545 (BYDAY, BYSETPOS,
  EXDATE, DST) es un pozo conocido; `rrule`/`rrule-temporal` ya lo resolvieron.
  Descartada (contradice buy-logic-headless).
- **Lib de calendario DOM (FullCalendar/Schedule-X).** Ya descartada en el
  research: no se comparte con React Native y pisa el design system.

## Notas de implementación (fuera del alcance de la decisión)

- El roadmap por fases (qué primero) vive en
  [`docs/planning/CALENDAR-PLAN.md`](../../planning/CALENDAR-PLAN.md). Este ADR
  congela el **modelo**, no el orden de ejecución.
- Las Fases 1–3 del plan (columnas, grilla, interacción) son **front-only** y no
  dependen de este ADR; solo lo necesitan las Fases 4 (modelo + recurrencia en
  core) y 5 (backend).
- La migración Alembic y el endpoint son backend (Fase 5) → **1 aprobación humana
  explícita en el PR** (regla #3 si toca `app/memory`/`alembic`).
