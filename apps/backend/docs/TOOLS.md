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
> `calendar.*` está **implementado de verdad** en la **pasada asíncrona del agente**
> (Fase E, ADR-021): escribe/lee la tabla `calendar_events` vía `CalendarEventStore`.
> `memory.*` está **implementado** (M7, mergeado).
>
> **Dos superficies, dos registries** (mismo patrón que `memory.*`):
> - `default_registry()` trae los `calendar.*` como **stubs `not_wired`** (cero efecto):
>   los consume el **playground observado** (ADR-019 D2, invariante de no-efecto).
> - `calendar_registry(store)` trae los `calendar.*` **reales** (con efecto), ligados
>   a `(session, user_id)`: los consume SOLO la pasada async del agente
>   (`app/workflows/agent_pass.py`). El `user_id` nunca viaja como argumento (el store
>   ya lo tiene; `extra='forbid'` lo impide), igual que la memoria.
>
> Las clases reales son `AgentCreateEventTool` / `AgentListEventsTool` (stateful);
> los stubs `CreateEventTool` / `ListEventsTool` se conservan para el playground.

### calendar.create_event

- **Descripción**: agendar un evento en el calendario del usuario.
- **Parámetros (tool real, espejan `EventCreate`)**:
  - `title: str` (no vacío)
  - `start_at: datetime` (ISO 8601 con timezone; rechaza epoch numérico)
  - `duration_min: int` (entero positivo; el fin del bloque es derivado)
  - `mode: str | None` (uno de los modos; opcional)
  - `location: str | None`
  - `time_zone: str | None`
  - `recurrence: list[str] | None` (RRULE; si no vacía, exige `time_zone` — ADR-018)
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
  `user_id` del store. **Idempotente**: deduplica por la tupla natural
  `(user_id, title, start_at, duration_min)` → un reintento de la pasada async NO
  agenda el evento dos veces. Devuelve el evento serializado (`id` + campos del wire,
  sin `user_id`/timestamps).
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

### reminder.set

- **Descripción**: crear un recordatorio.
- **Parámetros**:
  - `text: str`
  - `when: datetime` (ISO 8601 con tz)
- **Habilitada en modos**: productividad.

### reminder.list

- **Descripción**: listar los recordatorios del usuario.
- **Parámetros**:
  - `from_dt: datetime | None` (ISO 8601)
  - `to_dt: datetime | None`
- **Habilitada en modos**: productividad.

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

Ver `skills/add-llm-tool/SKILL.md`. En resumen:

1. Definir schema Pydantic en `app/llm/tools/<namespace>.py`.
2. Implementar la función ejecutora.
3. Registrarla en el router LLM con los modos donde aplica.
4. Documentarla acá.
5. Tests.
