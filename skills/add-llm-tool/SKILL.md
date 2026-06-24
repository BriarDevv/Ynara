# SKILL: Agregar una tool al agente Qwen

## Cuándo usar

Cuando hace falta que Qwen pueda ejecutar una acción nueva (ej:
`calendar.move_event`, `note.create`).

## Pre-requisitos

- La tool tiene un dueño en `apps/backend/app/services/` o
  equivalente — alguna lógica de negocio que ejecutar.
- Permisos / scopes claros: ¿qué modos pueden llamarla?
- Idempotencia decidida: ¿qué pasa si se llama dos veces con los
  mismos args?

## Paso a paso

1. **Schema Pydantic**. Definir args + response en
   `apps/backend/app/llm/tools/<namespace>.py`:
   ```python
   class CreateEventArgs(BaseModel):   # Pydantic v2 strict, extra="forbid"
       title: str
       start_at: IsoDatetime           # solo ISO 8601 con tz (rechaza epoch)
       duration_min: int               # el fin del bloque es derivado
   ```
2. **Clase `Tool`** (implementa el Protocol `Tool`: `namespace` / `name` /
   `to_spec` / `execute`). El `execute` valida con el schema, escribe vía el
   store de dominio y devuelve un `dict` o `tool_error(...)` — **nunca** `raise`
   (el `ToolRegistry` blinda, pero el contrato es no propagar):
   ```python
   class AgentCreateEventTool:          # ejemplo real: app/llm/tools/calendar.py
       namespace = "calendar"
       name = "calendar.create_event"
       async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
           ...
   ```
3. **Registro en la vía de producción**. Agregar el
   `namespace → builder` a `_AGENT_TOOL_BUILDERS` en
   `apps/backend/app/llm/tools/agent_registry.py` (lo consume
   `build_chat_tool_registry`, el tool-loop síncrono del chat — ADR-022)
   y habilitar el namespace en `ynara.config.json[modes][*].tools_enabled`.
   **NO** registrar en `default_registry()`: son los stubs `not_wired` del
   playground observado (ADR-019) y NO se ejecutan en el chat real.
4. **Documentación**. Agregar entrada en
   `apps/backend/docs/TOOLS.md` con descripción, args, modos,
   ejemplo, errores.
5. **Tests**. Test unitario del schema + test de integración del
   service.
6. **Frontend (si aplica)**. Si la tool produce "actions" visibles
   al usuario (ej: confirmación de evento agendado), agregar el
   componente correspondiente.
7. **PR**. Review humano.

## Errores posibles

Modelar los errores como respuesta estructurada, no excepción:

```json
{ "error": { "code": "overlap", "message": "Ya tenés algo agendado en ese horario." } }
```

Códigos comunes: `unauthorized`, `not_found`, `invalid_args`,
`overlap`, `rate_limited`.

## Checklist

- [ ] Schema Pydantic creado.
- [ ] Clase `Tool` con `execute` (devuelve dict / `tool_error`, nunca `raise`) + tests.
- [ ] Registrada en `_AGENT_TOOL_BUILDERS` (no `default_registry()`) + namespace en `tools_enabled`.
- [ ] `docs/TOOLS.md` actualizado.
- [ ] Frontend muestra la acción (si aplica).
- [ ] PR aprobado.
