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
   class CreateEventArgs(YnaraBaseModel):
       title: str
       start: datetime
       end: datetime
       attendees: list[str] | None = None
   ```
2. **Función ejecutora**. Implementar la función con type hints, que
   tome los args validados y devuelva el resultado:
   ```python
   async def create_event(args: CreateEventArgs, *, user_id: UUID) -> dict[str, Any]:
       ...
   ```
3. **Registro en el router**. Agregar la tool al catálogo del router
   LLM (`apps/backend/app/llm/router.py`), asociándola a los modos
   donde está habilitada.
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
- [ ] Función ejecutora con tests.
- [ ] Registro en router con modos correctos.
- [ ] `docs/TOOLS.md` actualizado.
- [ ] Frontend muestra la acción (si aplica).
- [ ] PR aprobado.
