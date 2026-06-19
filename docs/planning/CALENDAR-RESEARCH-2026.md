# Research: Calendario / Agenda — cómo se hace bien (2026)

> Deep-research (fan-out de búsquedas + verificación adversarial de claims) sobre cómo construir una feature de Calendario/Agenda con paridad web (Next.js) + mobile (Expo), cubriendo lógica de dominio Y frontend, para reemplazar lo que hay hoy en `apps/web/src/features/agenda` (mock-first, sin recurrencia/timezone/solapamientos).
> **Estado:** Bloque A (modelo/recurrencia/timezone) y el veredicto **verificados** (1ra pasada). Bloque B (front/UX fino), C (comparativa de libs + apps de referencia) y las open questions **resueltos en la 2da pasada** (2026-06-19): tres puntos clave fetch-verificados contra fuente primaria (a11y, `rrule-temporal`, Schedule-X) + el resto desde docs públicas/conocimiento de dominio establecido, marcado como tal.
> Convención: **[evidencia]** = respaldado por fuente verificada · **[conocimiento]** = bien establecido en docs públicas / dominio, no re-fetcheado en esta pasada · **[criterio]** = decisión/arquitectura nuestra · **[sin verificar]** = fuente encontrada, no confirmada.
> Generado: 2026-06-19 (1ra pasada) + ampliado 2026-06-19 (2da pasada). 1ra pasada: 24 fuentes → 115 claims → 25 verificados (24 confirmados, 1 refutado).

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

### 1.5 Sync offline / conflictos → **resuelto a alto nivel en §5.C** (2da pasada)

---

## 2. Frontend / UX — 2da pasada

### 2.1 Construcción de las vistas (Día/Semana/Mes/Agenda) **[conocimiento]**
Hay **dos motores de render distintos**, no uno parametrizado — conviene componentes separados:

- **Día / Semana = grilla de tiempo (time-grid).** Eje de tiempo vertical; cada día es una columna. Un evento *timed* se posiciona **absolute** sobre la columna:
  `top = (minutosDesdeInicioDía / minutosVisibles) * alturaContenedor` · `height = (duración / minutosVisibles) * alturaContenedor`.
  El **left/width** salen del algoritmo de columnas (§1.4, ya decidido). A la izquierda, una **gutter** con las etiquetas de hora. La **línea "ahora"** es un elemento en `top = minutosAhora/minutosVisibles * H`, refrescado **1×/min** (no por frame). Los eventos **all-day** y **multi-día** NO van en la grilla: van en una **franja horizontal arriba** del área scrolleable (no tienen posición por minuto). Así lo arman Google/Apple/Outlook, FullCalendar `timeGrid`, react-big-calendar y Schedule-X.
- **Mes = grilla de celdas.** CSS grid 6×7 (6 semanas fijas evita layout-shift al cambiar de mes). Eventos = barras horizontales; los multi-día **spannean** celdas. Cuando una celda desborda → **"+N more"** que abre popover o salta al Día. Es render **fundamentalmente distinto** al time-grid → componente aparte.
- **Agenda / Lista = lista cronológica** agrupada por día (headings de fecha + items). Es el render más simple, el más amigable a mobile, y el que **Ynara mobile ya usa**. Sin matemática de grilla. Sirve además como **equivalente accesible** del time-grid (ver §2.4).

### 2.2 Virtualización y performance **[conocimiento]**
- El time-grid de **un** día/semana está **acotado** (24h × ≤7 columnas) → **la grilla NO se virtualiza**. El costo real es (a) la cantidad de **nodos-evento** en el DOM y (b) el O(N²) del layout de solapamientos — pero los clusters son chicos, así que en la práctica no duele.
- Casos pesados: **Mes** con miles de eventos (lo mitiga el cap de **"+N more"** por celda) y **listas Agenda** largas (ahí **sí** windowing: `@tanstack/react-virtual` en web, `FlashList`/`FlatList` en RN).
- Técnicas: el layout es **puro** → `useMemo` keyeado por (rango visible + eventos); no recalcular en scroll; batch del "ahora" a 1×/min. Conclusión: **no virtualizar el time-grid; sí virtualizar listas largas y capear el Mes.**

### 2.3 Interacción **[conocimiento]** + ref. de comportamiento **[sin verificar]**
- **Web:** pointer events (`pointerdown/move/up`) + una pequeña máquina de estados de drag. *drag-to-create:* pointerdown en grilla vacía → arrastrar → bloque provisional **snappeado a 15min**. *drag-to-move:* agarrar el cuerpo. *resize:* handles arriba/abajo. **Snap** = `Math.round(min/15)*15`. *scroll-to-now:* al montar, scrollear a la línea "ahora" (o a horario laboral) **sin robar foco**. Comportamiento de referencia: [FullCalendar event drag/resize](https://fullcalendar.io/docs/event-dragging-resizing) [15].
- **La parte PURA va a core**, el binding de gestos NO (ver open question §5.B / resuelta).

### 2.4 Accesibilidad — **resuelto** (Higley + Roselli) **[evidencia, 2da pasada]**
El debate `role=grid` vs HTML semántico se resuelve con el **framework de Sarah Higley** (co-editora del APG) [22], que reconcilia el "anti-pattern" de Roselli [13]:
- **Tabla** si el fin es *consumir* información tabular; **grid** (`role=grid`) si el fin es *interactuar/editar* y te comprometés al **modelo de teclado completo** (un solo tab-stop + flechas + Home/End + PageUp/Down + roving tabindex). Higley advierte explícitamente contra los **"layout grids"** (visualmente cuadriculados pero sin relación fila/columna real) y contra el ejemplo "desafortunado" del propio APG que los trata como grid.
- **Aplicado a Ynara:**
  - **Mes** (celdas = fechas, navegación con flechas) → `role=grid` **es defendible** *si* implementamos el modelo de teclado completo (patrón date-picker del APG); si no, una tabla/estructura semántica alcanza.
  - **Día/Semana time-grid** (eventos absolute que **se solapan**) → `role=grid` es **mal fit** (no son celdas tabulares). Consenso 2024-2026: **HTML semántico** — cada evento es un `<button>` con nombre accesible ("Reunión, 9:00–10:00, Productividad"), agrupados por día con headings, y ofrecer la **vista Agenda/Lista como equivalente accesible** navegable por teclado. *scroll-to-now* no debe robar foco.

### 2.5 Responsive **[conocimiento]**
- **Semana (7 col) → mobile:** colapsa a **Día** (1 columna) con pager swipeable, o un 3-day. **Mes → mobile:** mini-mes + **Agenda/Lista debajo** (es el patrón "Schedule" de Google Calendar mobile). **Targets táctiles ≥44px** (WCAG 2.5.5 / Apple HIG). Ynara mobile ya tira a **Lista** → alineado.

## 3. Librerías / apps de referencia — 2da pasada

### 3.1 Tabla comparativa (estado 2026)
Schedule-X y rrule-temporal **fetch-verificados** esta pasada [22→Schedule-X repo, rrule-temporal repo]; el resto **[conocimiento]** (docs públicas).

| Lib | Licencia | DOM/RN | Recurrencia | Timezone | Drag/resize | Next App Router | Veredicto |
|---|---|---|---|---|---|---|---|
| **FullCalendar v6** | MIT core **+ premium pago** (timeline/resource) | DOM → **no RN** | vía plugin rrule | vía plugin | sí (built-in) | `"use client"` | descarta (DOM + pisa DS) |
| **Schedule-X** | **MIT** | DOM → **no RN** | sí (plugin) | sí | sí (algunos plugins premium) | `"use client"` | el "si fuera solo web" — pero **no RN** |
| **react-big-calendar** | MIT | DOM → **no RN** | **no nativa** (expandís vos) | vía adapter | addon DnD | `"use client"` | descarta |
| **@event-calendar** | MIT | DOM (Svelte→vanilla), bundle chico | parcial | sí | sí | `"use client"` | descarta (DOM) |
| **Toast UI Calendar** | MIT | DOM → **no RN** | sí | sí | sí | `"use client"` | descarta (mantenimiento lento) |
| **rrule.js** | MIT | **puro, RN ok** | RFC-5545 completa | **débil** (opera sobre `Date`/UTC) | — | ok (logic) | base, pero ojo DST |
| **rrule-temporal** | **MIT** ✓ | puro; **RN/Hermes sin documentar** | RFC-5545 **+ 7529** | **correcta** (Temporal `ZonedDateTime`) | — | ok (logic) | **engine recomendado** (spike Hermes) |
| **Temporal (TC39)** | — Stage 4 | polyfill RN/Safari | — | **correcta** | — | ok | base de tiempo |
| **date-fns / -tz** | MIT | puro, tree-shake | — | wrapper sobre `Intl` (display ok, no recurrencia) | — | ok | solo formateo |
| **Luxon** | MIT | puro, pesado | — | buena | — | ok | lo reemplaza Temporal |

**Confirmado esta pasada:** FullCalendar = **MIT + licencia comercial** para premium; Schedule-X = **MIT, core framework-agnostic + wrappers (React/Vue/Svelte/Angular/Preact), DOM-based → no sirve en React Native**, activo a 2026 (~2.4k stars); `rrule-temporal` = **MIT, sobre Temporal, `between(from,to)` para expandir por rango, requiere `@js-temporal/polyfill`, activo (v1.5.3 abr-2026, ~80k descargas/sem)**, RN/Hermes **no documentado**.

### 3.2 Cómo lo hacen las apps de referencia
**Hecho documentado** (APIs públicas) vs *inferencia* (clientes propietarios):
- **Google Calendar** — modelo = [Google Calendar API]: `start/end` con `timeZone` IANA, `recurrence` array de RRULE, `recurringEventId` + `originalStartTime` para overrides; el **server expande instancias**. Render web = **custom, sin lib de terceros** (*inferencia razonable*). **[evidencia (API) + inferencia]**
- **Apple Calendar / EventKit** — framework nativo `EKEvent`/`EKRecurrenceRule` (mapea a iCalendar), sync CalDAV. **[conocimiento]**
- **Outlook** — Microsoft Graph `event` con modelo de recurrencia equivalente (pattern + range), expansión server-side. **[conocimiento]**
- **Notion Calendar (ex-Cron)** / **Fantastical** — clientes custom sobre Google/iCloud/CalDAV; render propio. *Mayormente inferencia.* **[sin verificar]**
- **Patrón común (lo accionable):** **ninguna** usa una lib de UI de calendario de terceros; **todas** convergen en **iCalendar/RRULE + IANA tz + expansión de instancias server-side**. Esto **valida** nuestro veredicto (build-render / buy-logic-headless).

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
*(Refinado con la 2da pasada — los `←` son los ajustes nuevos.)*
1. **Columnas de solapamiento** en DayView/WeekView (función pura en core) — *quick win, arregla el bug visible, sin backend*. **← desde ya, exponer el equivalente accesible (lista de eventos como `<button>` con nombre accesible), que es el camino a11y del time-grid (§2.4) — barato si se hace junto.**
2. **Grilla completa**: 24h con scroll, **scroll-to-now** (sin robar foco), fila **all-day**, multi-día — *front*. **← all-day/multi-día van en franja propia ARRIBA del time-grid, no en la grilla (§2.1).**
3. **Interacción**: tap-para-abrir/editar → drag-crear/mover/resize — *front*. **← primero las funciones PURAS en core (px↔tiempo, snap-15, hit-test, clamp) worklet-safe; después el binding de gestos por plataforma (§5.B). NO virtualizar el time-grid; sí listas largas (§2.2).**
4. **Modelo + Temporal/rrule en core**: `time_zone`, `all_day`, `recurrence` (logic pura, testeable, mock-first). **← engine = `rrule-temporal` detrás de una interfaz fina `expand(event,range)`; SPIKE Hermes/RN temprano (§5.A).**
5. **Backend** `CalendarEvent` + `/v1/events` con expansión de instancias y overrides ("este" / "este y siguientes" / "serie", §5.C) — *gate regla #1 + ADR*.
6. **Vista Mes** — *front, al final*. **← componente APARTE (grilla de celdas 6×7 + "+N more"), no parametrizar el time-grid (§2.1). a11y: `role=grid` solo si se implementa el modelo de teclado completo, si no tabla semántica (§2.4).**

---

## 5. Open questions — resueltas (2da pasada)

**A. `rrule.js` + `Temporal` sin saltos de DST** → **resuelto [evidencia, 2da pasada].**
El footgun clásico es expandir con `rrule.js` (que opera en `Date`/UTC) y después shiftear: un recurrente "9:00 cada lunes" se corre 1h en el cambio de DST. **Recomendación:** usar **`rrule-temporal`** como engine de recurrencia en core — es Temporal-native (devuelve `Temporal.ZonedDateTime`), interpreta `TZID` y aplica DST con la base de zonas de Temporal, y expande por rango con `between(after, before, inclusive)`. Requiere `@js-temporal/polyfill` (que igual necesitamos en RN/Hermes + Safari). **Riesgo:** su soporte RN/Hermes **no está documentado** → **spike temprano**; mantener la expansión detrás de una **interfaz fina en core** (`expand(event, range) → Instance[]`) para poder swapear engine (p.ej. caer a `rrule.js` en floating + reproyección con Temporal) si Hermes falla.

**B. ¿Compartir la interacción drag/resize web↔RN?** → **resuelto [criterio, fundado en §2.3/2.4].**
Compartir la **matemática pura** en core (px↔tiempo, `snap` a 15min, hit-test de cluster/columna, clamp a límites del día, derivar nuevo `start/end` desde el delta) — y que esas funciones sean **worklet-safe** (como hicimos con LivingField). **No** compartir el binding de gestos: web = pointer events; RN = `react-native-gesture-handler` + Reanimated. Cada plataforma cablea sus gestos llamando a las puras de core.

**C. Sync offline / conflictos en recurrentes** → **resuelto a alto nivel [conocimiento].**
Optimistic updates con **cola local de mutaciones**; eventos con `version`/etag; al sincronizar, last-write-wins por campo o se expone conflicto. Overrides recurrentes (modelo iCalendar/Google): **"solo este"** = instancia override (`recurrence_id` + `original_start`); **"este y los siguientes"** = `UNTIL` en la RRULE vieja + serie nueva; **"toda la serie"** = editar el master. Detalle fino = **concern de backend (gateado, regla #1)**.

### Sigue pendiente (no era research)
- [ ] **ADR** para congelar `CalendarEvent` antes de tocar `apps/backend` (regla #1 + tablas). **← próximo paso natural.**
- Nota: claim **refutado** (1ra pasada): "start+duration mapea directo a iCalendar" — es legal (`DTSTART`+`DURATION`) pero no exime de agregar tz/all-day/recurrence.

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
| 22 | [Grids Part 1: To grid or not to grid — Sarah Higley](https://sarahmhigley.com/writing/grids-part1/) | primaria (a11y) |

> Fetch-verificadas en la 2da pasada (fuente primaria leída directo): **[22]** Sarah Higley (resuelve a11y), **[12]** [`rrule-temporal`](https://github.com/ggaabe/rrule-temporal) (MIT, Temporal, `between()`, polyfill, v1.5.3 abr-2026), **[17/Schedule-X repo]** ([github.com/schedule-x/schedule-x](https://github.com/schedule-x/schedule-x): MIT, DOM → no RN, activo).

---

> **Cómo se generó:** 1ra pasada = skill `deep-research` (5 ángulos → búsquedas en paralelo → fetch 24 fuentes → 115 claims → verificación adversarial 3-votos del top-25). **2da pasada (2026-06-19)** = research **directo sin fan-out de agentes** (el intento con workflow chocó con el límite de sesión y derrochó tokens): 3 búsquedas + 3 fetches a fuente primaria sobre los puntos de más valor (a11y, `rrule-temporal`, Schedule-X) + síntesis de conocimiento de dominio establecido, marcado como tal. **Para continuar: abrir el ADR de `CalendarEvent`** (único pendiente real; ya no queda research).
