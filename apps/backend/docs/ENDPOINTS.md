# ENDPOINTS.md — Catálogo de endpoints

> Por cada endpoint: método+path, descripción, request schema,
> response schema, permisos, rate limit, modo que lo usa.

## /v1/health

- **GET** `/v1/health`
- Liveness + readiness chequeable público.
- Request: ninguno.
- Response: `{ "status": "ok", "version": "0.1.0" }`.
- Permisos: público.
- Rate limit: 60/min.

## /v1/auth (TODO)

- TODO: completar cuando esté el módulo de auth.
- POST `/v1/auth/login`, `/v1/auth/refresh`, `/v1/auth/logout`.

## /v1/chat (TODO — M9)

Dos endpoints: uno no-streaming (JSON) y uno SSE. Contrato + justificación en
[`../../../docs/planning/RESPUESTAS-CONTRATO-CHAT.md`](../../../docs/planning/RESPUESTAS-CONTRATO-CHAT.md).

- **POST** `/v1/chat` (no-streaming):
  - Request: `{ text: string (límite ~4000 chars), mode: Mode, session_id?: UUID }`
  - Response: `{ text: string, actions: Action[], session_id: UUID }`
    - `actions` **siempre presente** (lista vacía si no hubo acciones; los modos
      Gemma nunca ejecutan tools). El Pydantic es `actions = []`, no opcional.
    - `Action = { id, name, arguments, result }` — `result` es el resultado
      ejecutado de la tool (o `{ error: { code, message } }`).
- **POST** `/v1/chat/stream` (SSE, `text/event-stream`):
  - Mismo request. Eventos con nombre: `token` `{ delta }`, `done`
    `{ session_id, actions, finish_reason }`, `error` `{ code, message }`.
  - Sin fallback mid-stream (M3); la infra caída se sirve como respuesta
    degradada (texto degradado por `token` + `done`), no como `error`.
- Permisos: usuario autenticado.
- Rate limit: TODO (probablemente 30/min por usuario).
- Modos: todos.

## /v1/memory (TODO)

- TODO: completar.
- GET `/v1/memory` — listar memoria del usuario, filtrable por capa.
- GET `/v1/memory/{id}` — detalle.
- PATCH `/v1/memory/{id}` — editar.
- DELETE `/v1/memory/{id}` — borrar.
- DELETE `/v1/memory` — borrar todo (dry-run + confirm).
- GET `/v1/memory/export` — export JSON estructurado.
- Permisos: usuario autenticado, solo su propia memoria.

## /v1/sessions (TODO)

- TODO: completar.

---

Toda ruta nueva agrega entrada acá en el mismo PR.
