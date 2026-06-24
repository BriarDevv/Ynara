# TOOLS.md — Catálogo de tools que Qwen puede llamar

> Por cada tool: nombre, descripción, parámetros (con Pydantic
> schema), modos donde está habilitada, ejemplo de invocación JSON,
> errores posibles.

## Convenciones

- Naming: `namespace.action` (snake_case en ambos).
- Cada tool tiene su schema Pydantic en
  `app/llm/tools/<namespace>.py`.
- Una tool no debe tener efectos colaterales fuera de los explícitos
  en su contrato.
- Tools siempre son **idempotentes cuando es posible** (ej: setear
  un recordatorio con la misma key no crea duplicados).
- Errores estructurados, no excepciones que escapen al modelo:
  `{ "error": { "code": "...", "message": "..." } }`.

## Tools disponibles

> **Estado**: `reminder.*` son stubs (esqueleto sin integración externa real).
> `calendar.*` y `task.*` están **implementados de verdad** y, desde **ADR-022**, se
> ejecutan **SÍNCRONOS en el chat de producción** (modo `productividad`): cuando qwen
> llama `calendar.create_event` / `task.create_task` durante un turno, la tool ESCRIBE
> en `calendar_events` / `tasks` dentro del turno (atómico con su commit) y el modelo
> confirma la acción en su respuesta. `memory.*` está **implementado** (M7, mergeado).
>
> **Tres superficies, tres registries** (mismo patrón para `calendar.*` / `task.*` /
> `memory.*`):
> - `default_registry()` trae los `calendar.*` / `task.*` como **stubs `not_wired`**
>   (cero efecto): los consume el **playground observado** (ADR-019 D2, invariante de
>   no-efecto). **Intacto** (ADR-022 no lo toca).
> - `build_chat_tool_registry(session, user_id, tools_enabled)`
>   (`app/llm/tools/agent_registry.py`) es el del **chat de producción** (ADR-022): trae
>   los `calendar.*` / `task.*` **reales** de los namespaces que el modo habilita en
>   `tools_enabled`, MÁS los stubs `not_wired` de `reminder` si está habilitado (sigue
>   sin backend real). Lo arma `build_memory_context` (`_default_reg`). Gateado
>   estrictamente por modo: para los modos gemma (`tools_enabled=[]`) queda vacío.
> - `calendar_registry(store)` / `task_registry(store)` / `_build_agent_registry(...)`
>   son los tools **reales** que usa la **pasada async del agente**
>   (`app/workflows/agent_pass.py`), hoy **dormant** (ADR-022 D5): registrada pero sin
>   encolador, reservada para una futura pasada en modos gemma.
>
> En las tres superficies el `user_id` nunca viaja como argumento (el store ya lo tiene;
> `extra='forbid'` lo impide), igual que la memoria.
>
> Las clases reales son `AgentCreateEventTool` / `AgentListEventsTool` /
> `AgentCreateTaskTool` / `AgentListTasksTool` (stateful); los stubs
> `CreateEventTool` / `ListEventsTool` / `CreateTaskTool` / `ListTasksTool` se conservan
> para el playground.

### calendar.create_event

- **Descripción**: agendar un evento en el calendario del usuario.
- **Parámetros (tool real, espejan `EventCreate`)**:
  - `title: str` (no vacío)
  - `start_at: datetime` (ISO 8601 con timezone; rechaza epoch numérico)
  - `duration_min: int` (entero positivo; el fin del bloque es derivado)
  - `mode: str | None` (uno de los modos; opcional)
  - `location: str | None`
  - `time_zone: str | None`
  - `recurrence: list[str] | None` (RRULE; si no vacía, exige `time_zone` — ADR-023)
- **Habilitada en modos**: productividad (los modos con `calendar` en `tools_enabled`).
- **Ejemplo**:
  ```json
  {
    "tool": "calendar.create_event",
    "args": {
      "title": "Tomar café con Carla",
      "start_at": "2026-05-20T15:00:00-03:00",
      "duration_min": 60
    }
  }
  ```
- **Efecto (tool real)**: INSERTA en `calendar_events` (status `confirmed`), atado al
  `user_id` del store. Desde ADR-022 corre **síncrona en el chat** (productividad): la
  escritura commitea atómica con el turno. **Idempotente**: deduplica por la tupla
  natural `(user_id, title, start_at, duration_min)` → un reintento (loop o futura
  pasada async) NO agenda el evento dos veces. Devuelve el evento serializado (`id` +
  campos del wire, sin `user_id`/timestamps).
- **Errores**: `invalid_arguments` (args malformados: título vacío, `duration_min` no
  positivo, fecha no-ISO/epoch, `user_id` u otro extra, `recurrence` sin `time_zone`).
- **Stub (playground observado)**: la versión del `default_registry()` valida args y
  devuelve `not_wired` (cero efecto). Sus params son `start`/`end`/`attendees` (shape
  histórico M6, observación pura).

### calendar.list_events

- **Descripción**: listar eventos en una ventana de tiempo.
- **Parámetros**:
  - `from_dt: datetime` (ISO 8601)
  - `to_dt: datetime`
- **Habilitada en modos**: productividad.
- **Efecto (tool real)**: lee `calendar_events` del usuario que arrancan en
  `[from_dt, to_dt)`, ordenados por `start_at` ASC. Devuelve `{ "events": [...] }`
  (eventos serializados, sin metadata interna). El stub del `default_registry()` sigue
  devolviendo `not_wired`.

### task.create_task

- **Descripción**: crear una tarea o pendiente del usuario (la prioridad del día).
- **Parámetros (tool real, espejan `TaskCreate`)**:
  - `title: str` (no vacío, máx 200 — cota LLM-fed)
  - `scheduled_at: datetime | None` (ISO 8601 con timezone; rechaza epoch numérico; opcional)
  - `duration_min: int | None` (entero positivo, máx 43200 — cota LLM-fed; opcional)
- **Habilitada en modos**: productividad (los modos con `task` en `tools_enabled`).
- **Ejemplo**:
  ```json
  {
    "tool": "task.create_task",
    "args": {
      "title": "Comprar pan",
      "scheduled_at": "2026-05-20T18:00:00-03:00",
      "duration_min": 15
    }
  }
  ```
- **Efecto (tool real)**: INSERTA en `tasks` (status `pending`), atado al `user_id` del
  store. Desde ADR-022 corre **síncrona en el chat** (productividad): la escritura
  commitea atómica con el turno. **Idempotente**: deduplica por la tupla natural
  `(user_id, title, scheduled_at)` (con `IS NULL` si no hay horario) → un reintento
  (loop o futura pasada async) NO crea el to-do dos veces. Devuelve la tarea serializada
  (`id` + campos del wire, sin `user_id`/timestamps).
- **Errores**: `invalid_arguments` (args malformados: título vacío o > 200,
  `duration_min` no positivo o > 43200, fecha no-ISO/epoch, `user_id` u otro extra).
- **Stub (playground observado)**: la versión del `default_registry()` valida args y
  devuelve `not_wired` (cero efecto). Sus params son `title`/`due` (shape de observación
  pura).

### task.list_tasks

- **Descripción**: listar las tareas/pendientes del usuario.
- **Parámetros**: ninguno (lista todas).
- **Habilitada en modos**: productividad.
- **Efecto (tool real)**: lee `tasks` del usuario (pending primero, luego por
  `scheduled_at` ASC). Devuelve `{ "tasks": [...] }` (tareas serializadas, sin metadata
  interna). El stub del `default_registry()` sigue devolviendo `not_wired`.

### reminder.set

- **Descripción**: crear un recordatorio.
- **Parámetros**:
  - `text: str`
  - `when: datetime` (ISO 8601 con tz)
- **Habilitada en modos**: productividad.
- **Estado**: **stub `not_wired`** incluso en el chat de producción (ADR-022): a
  diferencia de `calendar.*` / `task.*`, `reminder` no tiene backend real todavía (no
  hay tabla `reminders` ni scheduler). El modelo VE la tool (sigue en `tools_enabled`)
  pero llamarla no tiene efecto. Se "cablea" agregando su builder a
  `_AGENT_TOOL_BUILDERS` cuando exista el store.

### reminder.list

- **Descripción**: listar los recordatorios del usuario.
- **Parámetros**:
  - `from_dt: datetime | None` (ISO 8601)
  - `to_dt: datetime | None`
- **Habilitada en modos**: productividad.
- **Estado**: **stub `not_wired`** (ver `reminder.set`).

### memory.add

- **Descripción**: registrar un hecho nuevo en la memoria semántica del usuario. **No escribe de forma síncrona**: la consolidación es async (M8); el efecto es diferido. Devuelve confirmación inmediata con el detalle pendiente.
- **Parámetros**:
  - `content: str`
  - `layer: Literal["semantic"]` (hoy solo semántica; episódica/procedural van por el pipeline async de M8)
  - `importance: int | None` (0-100)
- **Habilitada en modos**: productividad, memoria. Se habilita vía el router (M8), no por `default_registry()`.

### memory.search

- **Parámetros**:
  - `query: str`
  - `limit: int = 5` (rango `[1, 20]`)
- **Búsqueda semantic-only**: no hay parámetro de capa; envuelve `SemanticMemoryStore` (solo memoria semántica).
- **Resultado**: `{ "results": [ { "id", "content", "importance" } ] }` — cada hit se proyecta
  con `_project_memory_result` (`memory.py`): solo `id` / `content` / `importance` (+ `score`
  si el reranker lo anota, forward-compat). **NUNCA** expone `user_id`, `source_session_id`,
  `created_at` ni `updated_at` (anti-PII / no regurgitar metadata interna, regla #4).
- **Habilitada en modos**: productividad, memoria.
- **Errores**: `invalid_arguments` (args malformados).

### memory.update

- **Parámetros**: `id: str`, `content: str`.
- **Resultado**: el mismo shape proyectado que `memory.search` — `{ "id", "content",
  "importance" }` (+ `score` si existe). Re-embeddea + re-cifra el hecho; nunca devuelve
  `user_id` / `source_session_id` / timestamps (regla #4).
- **Habilitada en modos**: productividad, memoria.
- **Errores**: `invalid_arguments` (args malformados o `id` que no es UUID); `not_found`
  (el `id` no existe o pertenece a otro usuario — mismo error, sin oráculo).

### memory.delete

- **Parámetros**: `id: str`.
- **Resultado**: `{ "deleted": true, "id": "<id>" }`. Hard-delete físico; el blob cifrado
  nunca viaja.
- **Habilitada en modos**: productividad, memoria.
- **Errores**: `invalid_arguments` (args malformados o `id` que no es UUID); `not_found`
  (el `id` no existe o pertenece a otro usuario — mismo error, sin oráculo).

### mode.switch

> **Estado: planeada — NO implementada todavía** (el cambio de modo hoy lo
> maneja el router, no una tool del LLM: `request.mode` entra como `Mode` en el
> request a `app/llm/router.py`; no existe `app/llm/tools/mode.py` ni se registra
> en `default_registry()`). El diseño de abajo queda como referencia para cuando
> se implemente como tool.

- **Descripción**: cambiar de modo (manual o sugerido por el agente).
- **Parámetros**: `target_mode: Literal["productividad", "estudio", "bienestar", "vida", "memoria"]`.
- **Habilitada en modos**: todos (sería la única tool global).

## Agregar una tool nueva

Playbook detallado: `skills/add-llm-tool/SKILL.md` (raíz del repo). En resumen, una
tool de agente **con efecto real en el chat de producción**:

1. Schema Pydantic de args en `app/llm/tools/<namespace>.py` (fechas con `IsoDatetime`).
2. Clase `Tool` con `execute` que devuelve el resultado o `tool_error(...)` — nunca `raise`.
3. Store de dominio + builder `<namespace>_registry(store)`.
4. **Registrar el `namespace → builder` en `_AGENT_TOOL_BUILDERS`** de
   `app/llm/tools/agent_registry.py` (la vía de PRODUCCIÓN, ADR-022: la consume
   `build_chat_tool_registry`). **NO** `default_registry()` (son solo los stubs `not_wired`
   del playground observado, ADR-019, cero efecto en el chat).
5. Habilitar el namespace en `ynara.config.json[modes][*].tools_enabled`.
6. Documentarla acá.
7. Tests (unit del schema/tool + integración del store).
