# Research: Calendario / Agenda — cómo se hace bien (2026)

> Deep-research (fan-out de búsquedas + verificación adversarial de claims) sobre cómo construir una feature de Calendario/Agenda con paridad web (Next.js) + mobile (Expo), cubriendo lógica de dominio Y frontend, para reemplazar lo que hay hoy en `apps/web/src/features/agenda` (mock-first, sin recurrencia/timezone/solapamientos).
> **Estado:** Bloque A (modelo/recurrencia/timezone) y el veredicto **verificados**. Bloque B (front/UX fino) y C (comparativa de libs + apps de referencia) quedaron con **fuentes pero sin verificar** — pendiente segunda pasada.
> Convención: **[evidencia]** = respaldado por fuentes verificadas adversarialmente · **[criterio]** = decisión/arquitectura nuestra · **[sin verificar]** = fuente encontrada, no confirmada.
> Generado: 2026-06-19. Verificación: 24 fuentes → 115 claims → 25 verificados (24 confirmados, 1 refutado).

---

## 0. Veredicto en una línea

**BUILD el render, BUY la lógica headless.** Construimos nosotros las vistas + el layout de solapamientos (en `@ynara/core` + render por plataforma); adoptamos libs chicas headless para lo difícil (`rrule.js` recurrencia, `Temporal` tiempo/timezone). **Ninguna lib de calendario DOM** (FullCalendar / Schedule-X / Toast UI): no se comparten con React Native y nos pisan el design system. **[criterio respaldado por evidencia]**

---

## 1. Lógica / funciones — VERIFICADO

### 1.1 Modelo de datos → estándar iCalendar/RFC 5545 (como Google) **[evidencia, alta]**
- Evento canónico = `DTSTART` + **uno** de `DTEND`/`DURATION`; `recurrence` = array de `RRULE`/`RDATE`/`EXDATE`; las instancias se **expanden** al renderizar un rango [1][2][3].
- **Matiz (claim refutado 0-3):** nuestro `start_at + duration_min` **es una forma iCalendar legal** (`DTSTART` + `DURATION`). O sea `duration_min` NO es el bug. Lo que falta: `time_zone`, `all_day`, `recurrence`, multi-día.
- All-day = fecha sin hora (`date` en vez de `dateTime`); timed = `dateTime` + offset [1][11].

### 1.2 Zona horaria → UTC solo NO alcanza; guardar IANA tz (wall-clock) **[evidencia, alta]**
- Un recurrente "9:00 cada lunes" debe quedar **9:00 local** aunque cambie DST; un offset fijo (o UTC pelado) lo corre. Google **exige** `timeZone` IANA en eventos con recurrencia [3].
- **Usar `Temporal` (TC39)** — **Stage 4 en marzo 2026** [4][7]. RN/Hermes y Safari aún sin nativo → `@js-temporal/polyfill`. Reemplaza `Date`/`date-fns-tz`/Luxon para esta lógica.

### 1.3 Recurrencia → RRULE + EXDATE/RDATE + overrides; expandir por rango **[evidencia, alta]**
- Serie = `RRULE`; excepciones = `EXDATE`/`RDATE`; "solo este" vs "toda la serie" = instancias **override separadas** (con `recurrence_id`/`original_start`) [2][3][6].
- Librería: **`rrule.js`** (RFC 5545, EXDATE/RDATE, recurrence-set) [5]. Variante moderna [`rrule-temporal`](https://github.com/ggaabe/rrule-temporal) combina recurrencia con Temporal [12].
- Para pintar una semana: expandir la serie a instancias concretas del rango [3].

### 1.4 Layout de solapamientos → clusters + columnas (BUILD, puro) **[evidencia media; atribución "Facebook" reputacional 2-1]**
Hoy `DayView` posiciona bloques `absolute` a ancho completo → los concurrentes **se pisan**. Algoritmo canónico [8][9][10][20]:
```
1. Ordenar eventos por inicio (y fin desc).
2. Agrupar en "clusters" de eventos que se solapan transitivamente.
3. Dentro del cluster, asignar cada evento a la PRIMERA columna cuyo
   último evento termine <= inicio del actual; si no, nueva columna.
4. width = 100% / nº columnas del cluster ; left = índiceColumna * width.
   (Refinamiento Google: expandir un evento a la derecha si no hay otro
    que lo bloquee.)
```
Es **puro y testeable** → va en `@ynara/core`, lo consumen DayView/WeekView (web + mobile).

### 1.5 Sync offline / conflictos — SIN claims verificados (pendiente)

---

## 2. Frontend / UX — SIN VERIFICAR (fuentes encontradas)
- **a11y:** patrón **APG grid** del W3C para teclado [14], con advertencia: ["ARIA grid as an anti-pattern"](https://adrianroselli.com/2020/07/aria-grid-as-an-anti-pattern.html) — a menudo conviene HTML semántico antes que `role=grid` [13].
- **drag/resize:** doc de [FullCalendar event drag/resize](https://fullcalendar.io/docs/event-dragging-resizing) como referencia de comportamiento [15].
- **comparativa de schedulers React:** [LogRocket](https://blog.logrocket.com/best-react-scheduler-component-libraries/) [16].
- Pendiente verificar: construcción de vistas Día/Semana/Mes/Agenda, virtualización con muchos eventos, scroll-to-now, navegación, responsive desktop→mobile.

## 3. Librerías / apps de referencia — SIN VERIFICAR
- Único punto **verificado y accionable**: lib DOM ≠ compartible con RN → cross-platform pide headless + render propio.
- Fuentes crudas (no comparadas con claims): [Schedule-X recurrence](https://schedule-x.dev/docs/calendar/plugins/recurrence) [17], [react-native-calendars (Wix)](https://github.com/wix/react-native-calendars) [18], [builder.io best React calendar](https://www.builder.io/blog/best-react-calendar-component-ai) [19].
- Pendiente: tabla comparativa (FullCalendar / Schedule-X / react-big-calendar / Toast UI: licencia, tamaño, headless, recurrencia/tz/drag, SSR App Router, RN) y cómo lo hacen Google/Apple/Notion/Fantastical/Outlook.

---

## 4. Recomendación para Ynara **[criterio]**

### 4.1 Arquitectura (core puro vs render)
- **`@ynara/core` (puro, web+mobile):** modelo `CalendarEvent`, expansión de recurrencia (`rrule.js`), tiempo/timezone (`Temporal`), y el **algoritmo de columnas** como función pura `layout(events) → {col, cols}`.
- **Render por plataforma:** `DayView`/`WeekView`/`MonthView` en web (grilla + design system) y en RN aparte, ambos consumiendo los helpers puros de core. (ADR-012: core ya tiene hooks de Agenda compartidos, sin lib de fecha.)

### 4.2 Evolución del modelo `AgendaEvent` → `CalendarEvent`
- Agregar `time_zone` (IANA), `all_day` (bool; si true → fecha sin hora), `recurrence` (array RRULE/RDATE/EXDATE) + `recurrence_id`/`original_start` para overrides, y soporte multi-día.
- `duration_min` puede quedar (es legal iCalendar), pero el server debe poder **expandir instancias**.
- `/v1/events?from&to` debe devolver **instancias ya expandidas** del rango + permitir editar "este" vs "la serie". (Hoy `agenda.ts` está PROVISIONAL/mock; no existe `CalendarEvent` ni el endpoint.)

### 4.3 Roadmap incremental (front primero — no necesita backend)
1. **Columnas de solapamiento** en DayView/WeekView (función pura en core) — *quick win, arregla el bug visible, sin backend*.
2. **Grilla completa**: 24h con scroll, **scroll-to-now**, fila **all-day**, multi-día — *front*.
3. **Interacción**: tap-para-abrir/editar → drag-crear/mover/resize — *front*.
4. **Modelo + Temporal/rrule en core**: `time_zone`, `all_day`, `recurrence` (logic pura, testeable, mock-first).
5. **Backend** `CalendarEvent` + `/v1/events` con expansión de instancias y overrides — *gate regla #1 + ADR*.
6. **Vista Mes** — *front, al final*.

---

## 5. Para continuar (open questions + qué falta)
- [ ] **Segunda pasada de research** que verifique Bloque B (vistas/drag/virtualización/a11y/responsive) y Bloque C (comparativa real de libs + cómo lo hacen Google/Apple/Notion/Fantastical/Outlook).
- [ ] Combinar `rrule.js` (trabaja en `Date`/UTC) con `Temporal` en wall-clock + TZID sin saltos de DST.
- [ ] Patrón a11y exacto (APG grid vs HTML semántico) + virtualización; ¿compartir interacción drag/click entre web y RN/Reanimated?
- [ ] **ADR** para congelar `CalendarEvent` antes de tocar `apps/backend` (regla #1 + tablas).
- [ ] Sync offline / conflictos en recurrentes con overrides "este vs serie".
- [ ] Claim **refutado** (anotado): "start+duration mapea directo a iCalendar" — es legal pero no exime de agregar tz/all-day/recurrence.

---

## 6. Fuentes

| # | Fuente | Tipo |
|---|--------|------|
| 1 | [Google Calendar API – Events & calendars](https://developers.google.com/workspace/calendar/api/concepts/events-calendars) | primaria |
| 2 | [RFC 5545 (iCalendar)](https://datatracker.ietf.org/doc/html/rfc5545) | primaria |
| 3 | [Google – Recurring events](https://developers.google.com/workspace/calendar/api/guides/recurringevents) | primaria |
| 4 | [Temporal Reaches Stage 4 (Igalia, mar-2026)](https://www.igalia.com/2026/03/13/Temporal-Reaches-Stage-4.html) | primaria |
| 5 | [rrule.js](https://github.com/jkbrzt/rrule) | primaria |
| 6 | [Nylas – Events & RRULEs](https://www.nylas.com/blog/calendar-events-rrules/) | blog |
| 7 | [JS Temporal, is it here? (Bryntum)](https://bryntum.com/blog/javascript-temporal-is-it-finally-here/) | blog |
| 8 | [calendar-puzzle](https://github.com/taterbase/calendar-puzzle) | repo |
| 9 | [Gist: algoritmo de layout (aholachek)](https://gist.github.com/aholachek/ce7cd491546a88cbc9c4) | gist |
| 10 | [Google Calendar Day View HLD (dev.to)](https://dev.to/arghya_majumder/google-calendar-day-view-hld-f9n) | blog |
| 11 | [Google API – EventDateTime](https://developers.google.com/resources/api-libraries/documentation/calendar/v3/java/latest/com/google/api/services/calendar/model/EventDateTime.html) | primaria |
| 12 | [rrule-temporal](https://github.com/ggaabe/rrule-temporal) | repo |
| 13 | [ARIA grid as an anti-pattern (Roselli)](https://adrianroselli.com/2020/07/aria-grid-as-an-anti-pattern.html) | blog |
| 14 | [W3C APG – Grid pattern](https://www.w3.org/WAI/ARIA/apg/patterns/grid/) | primaria |
| 15 | [FullCalendar – event drag/resize](https://fullcalendar.io/docs/event-dragging-resizing) | primaria |
| 16 | [LogRocket – best React scheduler libs](https://blog.logrocket.com/best-react-scheduler-component-libraries/) | blog |
| 17 | [Schedule-X – recurrence plugin](https://schedule-x.dev/docs/calendar/plugins/recurrence) | primaria |
| 18 | [react-native-calendars (Wix)](https://github.com/wix/react-native-calendars) | repo |
| 19 | [builder.io – best React calendar](https://www.builder.io/blog/best-react-calendar-component-ai) | blog |
| 20 | [facebook-calendar (layout puzzle)](https://github.com/JayHuang/facebook-calendar) | repo |
| 21 | [DayFlow: React calendar con Temporal + DnD](https://dev.to/juncai_li_935da984029ca0f/building-dayflow-a-modern-react-calendar-library-with-temporal-api-and-advanced-drag-and-drop-2c27) | blog |

---

> **Cómo se generó:** skill `deep-research` (5 ángulos → búsquedas en paralelo → fetch 24 fuentes → 115 claims → verificación adversarial 3-votos del top-25). El detalle del run quedó en el transcript de la sesión. Para continuar: correr la segunda pasada sobre B y C, y abrir el ADR de `CalendarEvent`.
