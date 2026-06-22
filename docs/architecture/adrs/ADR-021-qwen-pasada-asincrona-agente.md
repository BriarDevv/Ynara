# ADR-021: Pasada asíncrona del agente qwen (memoria + tools por detrás de gemma)

## Estado

Propuesto — **parcialmente superseded por [ADR-022](./ADR-022-tools-sincronos-en-chat.md)**

> ADR-022 mueve la EJECUCIÓN de las tools de agente (`calendar`/`task`) del path
> ASÍNCRONO descrito acá al tool-loop SÍNCRONO del chat de producción, para la config
> de modos actual (las tools corren en el turno, atómicas con su commit, y el modelo
> confirma la acción en su respuesta). La pieza de **memoria** de este ADR
> (`consolidate_turn`, gateada por `writes_memory`) sigue vigente y async. La task
> `agent_turn_pass` queda **dormant** (registrada pero sin encolador), reservada para
> una futura pasada de agente en modos gemma.

<!-- Autonomía dada por @BriarDevv (CODEOWNER) el 2026-06-22 ("hacete vos una hoja
     de ruta, lo que hagas que sea la mejor práctica y lo más escalable posible,
     total confianza, no es necesario que me pidas permiso"). Lleva el tool-loop
     OBSERVADO de ADR-019 a EJECUCIÓN REAL asíncrona en el chat de producción. -->

## Fecha

2026-06-22

## Contexto

La visión del producto (confirmada por el usuario): el usuario **conversa con gemma**
(modelo conversacional, respuesta rápida en streaming); **qwen corre por detrás**
para anotar memoria, **agendar eventos**, poner recordatorios y usar tools, a
partir de lo que se conversó. En palabras del dueño: *"hablamos con gemma mientras
qwen le pega una pasada a lo hablado y anota si hay que anotar, agenda si hay que
agendar, y usa la tool si hay que usarla"*.

Hechos verificados del código que hacen esto realizable hoy:

- **La consolidación de memoria YA es asíncrona** (Celery): `consolidate_turn`
  (semántica + procedural) se encola post-commit en los modos qwen
  (`ChatService._enqueue_consolidation`, gateado por `writes_memory`), y
  `consolidate_session` (episódica) al cerrar la sesión. El patrón "pasada qwen por
  detrás, async, best-effort fail-open" ya existe y está probado.
- **El tool-loop existe y está OBSERVADO** (ADR-019): `run_tool_loop(...)` devuelve
  `actions` (`{id, name, arguments, result}` por iteración), acotado por
  `MAX_TOOL_ITERATIONS = 5`. El playground admin lo corre con **cero efecto**
  (`registries=(default_registry(), None)`): `default_registry()` trae solo
  `calendar`/`reminder` como **stubs `not_wired`**; las tools con escritura real
  (`memory.update`/`delete`) viven en `memory_registry()`, opt-in.
- **La agenda ya tiene tabla real**: `calendar_events` + modelo `CalendarEvent`
  (ADR-018 / PR #402). O sea, `calendar.create_event` ya tiene **dónde escribir**.
- **El catálogo de modos es config-driven**: `ynara.config.json` declara por modo
  `tools_enabled[]` y `writes_memory` (expuesto en `GET /v1/modes`).

Lo que falta: **ejecutar ese tool-loop de verdad** (no observado) para que las
acciones (agendar/recordar) tengan efecto, sin romper la latencia del chat.

## Decisión

### D1 — La pasada del agente es ASÍNCRONA, no síncrona en el request del chat

Una nueva task Celery (`agent_turn_pass`) se encola **post-commit** después de
persistir el turno (mismo punto y semántica best-effort fail-open que
`consolidate_turn`). **No** se corre el tool-loop dentro del request del chat.

Razón (escalabilidad): gemma ya responde y streamea; correr un tool-loop de qwen
(hasta 5 iteraciones de inferencia + tools) dentro del request acoplaría la
latencia del chat a la del agente y bloquearía la UX. La pasada async desacopla,
**escala horizontal con workers**, y reusa el patrón ya probado de consolidación.

### D2 — Tools reales detrás de una interfaz, gateadas por config de modo

- Se implementan de verdad las tools hoy `not_wired`: `calendar.create_event`
  (escribe `calendar_events` vía el modelo `CalendarEvent`), `calendar.list_events`,
  y `reminder.*` (depende del backend de reminders — fase posterior).
- **Qué tools corren lo decide `tools_enabled` del modo** (ya en `ynara.config.json`
  / `GET /v1/modes`), no el código. Agregar/quitar una tool de un modo es un cambio
  de config, no de código → escalable.
- La pasada usa el `user_id` real + un `DbSession` con **efecto real** (a diferencia
  del playground observado de ADR-019). Las escrituras respetan el aislamiento por
  usuario y se auditan donde corresponda.

### D3 — Separación de responsabilidades (single responsibility)

- `consolidate_turn` (memoria) **queda como está**, gateado por `writes_memory`.
- `agent_turn_pass` (tools/acciones) es una **task separada**, gateada por
  `tools_enabled` del modo.
- Ambas async, ambas qwen, ambas post-commit. Se escalan, monitorean y reintentan
  **independientemente** (una falla de tools no afecta la consolidación de memoria,
  y viceversa).

### D4 — Superficie de las acciones hacia el usuario

Como la pasada es async, las acciones **no** están listas en el `done` del chat.
Se **persisten** (el evento queda en `calendar_events`) y se surfacean por:
(a) la **agenda** se actualiza (el usuario ve el evento creado), y
(b) un **feed de avisos/notificaciones** (Fase F) que lista "agendé X / te recordé Y".
Para v1 alcanza con persistir + que la agenda lo refleje; el feed de avisos es la
superficie dedicada de feedback inmediato (fase posterior).

### D5 — "Memoria/tools siempre" → resuelto por CONFIG, no hardcode

La duda pendiente ("¿memoria/tools en todos los modos o solo en algunos?") se
resuelve **data-driven**: el control es `writes_memory` + `tools_enabled` por modo
en `ynara.config.json`. NO se hardcodea "siempre". Si el producto quiere memoria o
agendado en todos los modos, se cambia la **config** (y los modos gemma podrían
declarar `tools_enabled: ["calendar"]` sin tocar una línea de código). Esto es lo
escalable y mantiene la decisión en manos del producto, no del código.

## Invariantes y seguridad

- **Regla #4**: en cualquier `except`, loguear solo `type(exc).__name__` (nunca
  datos del usuario ni `str(exc)`).
- **Acotación / idempotencia**: `MAX_TOOL_ITERATIONS = 5`; la pasada debe ser
  idempotente ante reintentos de Celery (dedupe por `turn_id` / idempotencia de la
  tool), para no agendar el mismo evento dos veces.
- **Aislamiento**: toda escritura de tool filtra/asocia por `user_id` real.
- **Tests**: con `FakeLlmClient` guionado (tool_calls determinísticas) se verifica
  que `calendar.create_event` crea el evento del usuario correcto; y que un modo
  sin la tool en `tools_enabled` **no** la ejecuta.

## Consecuencias positivas

- Latencia del chat intacta: gemma responde ya; el agente escala aparte.
- Reusa infra probada: Celery, `run_tool_loop`, registries, `calendar_events`.
- Config-driven (`tools_enabled` / `writes_memory`) → se extiende sin tocar código.
- Single-responsibility: memoria y tools se operan/escalan por separado.

## Consecuencias negativas

- Las acciones son **eventuales** (no instantáneas en la respuesta) → para feedback
  inmediato hace falta la superficie de avisos (Fase F).
- `reminder.*` necesita su backend (tabla `reminders` + scheduler) — fase posterior.
- **Dependencia operacional**: requiere el worker Celery (y beat para lo agendado/
  recaps) arriba. La auditoría de backend marcó **`celery beat no deployado` como
  CRITICAL** → hay que resolverlo para que esta pasada y los recaps anden en prod.

## Alternativas descartadas

- **Tool-loop SÍNCRONO en el chat**: bloquea la UX y acopla la latencia del chat a
  la del agente; no escala. Descartada.
- **"Memoria/tools siempre" hardcodeado**: rompe el control por modo y la
  escalabilidad config-driven. Descartada (se hace por config, D5).
- **Una sola task que hace memoria + tools**: viola single-responsibility y complica
  reintentos/monitoreo independientes. Descartada (tasks separadas, D3).

## Relación con otros ADRs

- **Refina** [ADR-019](./ADR-019-playground-agente-observado.md): lleva el tool-loop
  observado (cero efecto) a **ejecución real async** en el chat de producción.
- **Usa** [ADR-018](./ADR-018-calendar-event-model.md): `calendar.create_event`
  escribe en `calendar_events`.
- Se apoya en el patrón de consolidación asíncrona de memoria
  ([ADR-010](./ADR-010-memory-architecture-v2.md) /
  [ADR-007](./ADR-007-memory-decay-retention-encryption.md)).
- Hereda de [ADR-002](./ADR-002-gemma-qwen-dual-stack.md) el ruteo por modo
  (gemma conversacional / qwen agente).
