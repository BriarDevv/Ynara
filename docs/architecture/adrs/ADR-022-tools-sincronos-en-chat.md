# ADR-022: Tools de agente síncronas en el chat de producción (supersede parcial de ADR-021)

## Estado

Aceptado — refina/supersede parcialmente [ADR-021](./ADR-021-qwen-pasada-asincrona-agente.md)

<!-- Autonomía dada por @BriarDevv (CODEOWNER) el 2026-06-22 ("hacete vos una hoja
     de ruta, lo que hagas que sea la mejor práctica y lo más escalable posible,
     total confianza"). Este ADR corrige el BUG de que el chat real recibía los stubs
     `not_wired` y lleva las tools reales (calendar/task) al tool-loop del chat. -->

## Fecha

2026-06-22

## Contexto

ADR-021 diseñó la ejecución de las tools de agente (`calendar`/`task`) como una
**pasada asíncrona** (`agent_turn_pass`) encolada post-commit: "qwen por detrás de
gemma". Sin embargo, dos hechos verificados del código revelan que ese diseño NO
encaja con la config de modos actual y dejaba un bug en el camino crítico del chat:

- **Bug en el chat real**: el tool-loop de producción
  (`ChatService.run_turn → route() → build_memory_context → run_tool_loop`) recibía
  `_default_reg = default_registry()`, que trae los **stubs `not_wired`** de
  `calendar`/`reminder`/`task`. O sea: cuando qwen llamaba `calendar.create_event`
  durante un turno de `productividad`, recibía *"la funcionalidad todavía no está
  operativa"* y NO se creaba nada. El usuario nunca veía el evento agendado.

- **El modelo que razona tools es el MISMO que conversa**: en la config actual de modos
  (`ynara.config.json`), el único modo con tools accionables (`productividad`) usa
  **qwen** como modelo conversacional. No hay un "gemma adelante, qwen atrás": qwen ya
  está en el path del request y puede razonar el tool call inline. Una pasada async
  separada significaría correr qwen **dos veces** por turno (una conversando, otra
  accionando) sin beneficio.

- **Las semánticas de commit ya son correctas para una escritura síncrona**: las tools
  reales (`AgentCreateEventTool` etc.) escriben vía stores que hacen `flush` (no
  `commit`); `run_turn` hace `self._session.commit()` al final. Una escritura de tool en
  `route()` (misma sesión) commitea **atómica** con el turno. Además
  `CalendarEventStore.create_event` / `TaskStore.create_task` ya son **idempotentes**
  (dedup por tupla natural) y devuelven un dict JSON-safe.

- **La invariante del playground (ADR-019) NO debe tocarse**: el playground admin arma
  su propio `default_registry()` directo (cero efecto, "observado"). Cualquier cambio
  acá no puede pasar por `default_registry()` ni por el playground.

## Decisión

### D1 — Las tools de agente se ejecutan SÍNCRONAS en el tool-loop del chat

El tool-loop de producción del chat ejecuta las tools de agente **reales**
(`calendar`/`task`) durante el turno, sobre la misma `AsyncSession`. La escritura se
commitea atómica con el turno (`run_turn` hace un único `commit` al final). El modelo
puede así **confirmar la acción en su propia respuesta** ("listo, te agendé el
dentista..."), porque la tool ya devolvió un resultado real (con `id`) en la misma
iteración.

Esto **supersede, para la config de modos actual, la ejecución async-only de ADR-021**:
las tools ya no se accionan por detrás; se accionan en el turno.

### D2 — Registry del chat ≠ registry del playground ≠ registry de la pasada async

Se introduce `build_chat_tool_registry(session, user_id, tools_enabled)` en el hogar
canónico `app/llm/tools/agent_registry.py` (capa `llm.tools`). `build_memory_context`
arma `_default_reg` con esta función (antes usaba `default_registry()`). Tres registries,
tres superficies:

| Superficie | Registry | Efecto |
|---|---|---|
| Playground (ADR-019) | `default_registry()` | **Cero** (stubs `not_wired`), observado |
| Chat de producción (este ADR) | `build_chat_tool_registry()` | **Real** (calendar/task) + stub reminder |
| Pasada async (ADR-021, dormant) | `_build_agent_registry()` | Real (calendar/task) |

`default_registry()` y el playground quedan **intactos** (invariante ADR-019).

### D3 — Gating estricto por modo (config-driven, sin hardcode)

Una tool de agente solo se construye/expone si su namespace está en
`mode_cfg.tools_enabled` (`ynara.config.json`). Mismo gate que ADR-021. Efecto neto con
la config actual: `calendar`/`task` reales solo existen en `productividad`; los modos
gemma (`tools_enabled=[]`) obtienen un registry vacío; `memoria` (`[memory]`) no trae
calendar/task (el namespace `memory` lo maneja `_memory_reg` aparte).

### D4 — `reminder` sigue siendo stub `not_wired`

`reminder` está en `tools_enabled` de `productividad`, pero **no tiene backend real
todavía** (no existe tabla `reminders` ni scheduler). `build_chat_tool_registry`
registra los stubs `SetReminderTool`/`ListRemindersTool` cuando el modo habilita
`reminder`: el modelo sigue **viendo** la tool (el contrato no cambia) pero llamarla no
tiene efecto, igual que antes. Cuando `reminder` tenga store real, se suma su builder a
`_AGENT_TOOL_BUILDERS` y deja de tratarse como stub, sin tocar el resto del flujo.

### D5 — `agent_turn_pass` queda DORMANT (no se borra)

`ChatService` ya NO encola `agent_turn_pass` (seguir encolándola dispararía qwen dos
veces por turno). Pero la task se **mantiene registrada** (`app/workflows/__init__.py`
+ `tests/workers/test_task_registration.py`) y funcional: queda reservada para una
**futura pasada de agente en modos gemma**, donde el modelo conversacional no razona
tool calls inline y conviene una pasada qwen por detrás. El mapping/builder canónico
(`_AGENT_TOOL_BUILDERS` / `_build_agent_registry`) se compartió en `agent_registry.py`
y `agent_pass` los re-importa.

## Invariantes y seguridad

- **Atomicidad**: la escritura de la tool y el turno commitean juntos (un solo `commit`
  en `run_turn`). Si un bug inesperado salta antes del commit, `get_db()` hace rollback
  y nada se persiste (ni evento ni turno).
- **`user_id` nunca viaja como argumento**: el store ya está ligado a `(session,
  user_id)`; `extra='forbid'` en los args de las tools reales lo bloquea (no se puede
  agendar para otro usuario).
- **Playground intacto (ADR-019)**: `default_registry()` y la construcción del
  playground no se tocan; sigue corriendo el tool-loop a cero efecto.
- **Regla #4 (logs)**: ningún log nuevo loguea contenido de usuario / args / `str(exc)`;
  solo `type(exc).__name__` donde aplica.
- **Idempotencia**: heredada de los stores (dedup por tupla natural), por si el loop
  reintenta una tool dentro del mismo turno.

## Consecuencias positivas

- El chat real **acciona de verdad**: agenda eventos y crea tareas en el turno, y el
  modelo lo confirma en su respuesta (UX correcta, fin del bug `not_wired`).
- Un solo `route()`/qwen por turno (no se duplica el modelo).
- Latencia de acción nula respecto del turno (no hay espera del worker async).
- Diseño escalable: agregar una tool de agente con backend real es una entrada en
  `_AGENT_TOOL_BUILDERS` + el namespace en `tools_enabled`.

## Consecuencias negativas (tradeoffs conocidos)

- **Latencia del turno** absorbe el tiempo de la tool (DB write). Acotado y barato para
  calendar/task.

### Resuelto: escritura flusheada + degradación del LLM (SAVEPOINT)

La versión inicial de este ADR aceptaba como tradeoff que una tool flusheara una
escritura y luego el LLM degradara: la escritura commiteaba igual con el turno (un evento
fantasma sin un turno de conversación que lo confirme). Eso se **corrigió**:
`ChatService.run_turn` envuelve `route()` en un `session.begin_nested()` (SAVEPOINT).
`route()` nunca propaga el `LlmError` (devuelve `finish_reason='degraded'`), así que el
savepoint cubre **todos** los puntos donde `route()` captura el error —no solo "una
iteración posterior del loop". En un turno degradado se hace `rollback()` del nested, que
descarta SOLO las escrituras de tools; la `ChatSession` (flusheada por el router fuera del
savepoint) sobrevive como ancla de la sesión. En el camino feliz se libera el SAVEPOINT y
el commit único persiste todo atómico. Resultado: ya no hay desajuste DB-tiene-evento /
`conversation_turns`-vacío en un turno degradado.

## Alternativas descartadas

- **Mantener la ejecución async-only (ADR-021 puro)**: dejaba el bug `not_wired` en el
  chat y duplicaba qwen. Descartada para la config actual.
- **Tocar `default_registry()` para que traiga las tools reales**: rompería la
  invariante de cero-efecto del playground (ADR-019). Descartada: por eso se introduce un
  registry separado (`build_chat_tool_registry`).
- **Borrar `agent_turn_pass`**: cierra la puerta a la pasada de agente en modos gemma.
  Descartada: queda dormant.

## Relación con otros ADRs

- **Supersede parcialmente ADR-021**: mueve la ejecución de tools del async al síncrono
  para la config actual; la memoria (`consolidate_turn`) de ADR-021 sigue async.
- **Respeta ADR-019**: playground observado a cero efecto, intacto.
- **Reusa ADR-023**: las tablas `calendar_events` / `tasks` ya existen; este ADR no
  agrega migraciones.
- **Config-driven (ADR-002 / catálogo de modos)**: el gate es `tools_enabled` por modo.
