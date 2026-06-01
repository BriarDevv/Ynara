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

> **Estado**: `calendar.*` y `reminder.*` son stubs (esqueleto sin integración externa real). `memory.*` está **implementado** (M7, mergeado). Las tools `memory.*` **no están en `default_registry()`**: se construyen con `memory_registry(semantic_store)` y el router (M8) las combina por modo cuando la memoria está habilitada.

### calendar.create_event

- **Descripción**: agendar un evento en el calendario del usuario.
- **Parámetros**:
  - `title: str`
  - `start: datetime` (ISO 8601, con timezone)
  - `end: datetime`
  - `attendees: list[str] | None` (emails)
- **Habilitada en modos**: productividad.
- **Ejemplo**:
  ```json
  {
    "tool": "calendar.create_event",
    "args": {
      "title": "Tomar café con Carla",
      "start": "2026-05-20T15:00:00-03:00",
      "end": "2026-05-20T16:00:00-03:00"
    }
  }
  ```
- **Errores posibles**: `calendar_unauthorized`, `overlap`, `invalid_time`.

### calendar.list_events

- **Descripción**: listar eventos en una ventana de tiempo.
- **Parámetros**:
  - `from_dt: datetime`
  - `to_dt: datetime`
- **Habilitada en modos**: productividad, vida.

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
- **Habilitada en modos**: productividad, memoria.

### memory.update

- **Parámetros**: `id: str`, `content: str`.
- **Habilitada en modos**: memoria.

### memory.delete

- **Parámetros**: `id: str`.
- **Habilitada en modos**: memoria.

### mode.switch

- **Descripción**: cambiar de modo (manual o sugerido por el agente).
- **Parámetros**: `target_mode: Literal["productividad", "estudio", "bienestar", "vida", "memoria"]`.
- **Habilitada en modos**: todos (es la única tool global).

## Agregar una tool nueva

Ver `skills/add-llm-tool/SKILL.md`. En resumen:

1. Definir schema Pydantic en `app/llm/tools/<namespace>.py`.
2. Implementar la función ejecutora.
3. Registrarla en el router LLM con los modos donde aplica.
4. Documentarla acá.
5. Tests.
