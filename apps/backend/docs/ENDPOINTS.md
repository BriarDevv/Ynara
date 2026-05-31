# ENDPOINTS.md — Catálogo de endpoints

> Por cada endpoint: método+path, descripción, request schema,
> response schema, permisos, rate limit, modo que lo usa.

## /v1/health

- **GET** `/v1/health` — **liveness**: el proceso está vivo. No toca dependencias.
  - Request: ninguno.
  - Response: `{ "status": "ok", "version": "0.1.0" }` (siempre 200 si responde).
  - Permisos: público. Rate limit: 60/min.
- **GET** `/v1/health/ready` — **readiness**: pinga DB y Redis.
  - Request: ninguno.
  - Response 200: `{ "status": "ready", "version": "0.1.0", "checks": { "database": { "ok": true }, "redis": { "ok": true } } }`.
  - Response 503 (degraded): mismo shape, `status: "degraded"` y la dependencia caída con `{ "ok": false, "error": "<ClaseDeExcepción>" }`. El error es **solo el nombre de la clase**, nunca el connection string (regla #2 / #4).
  - Permisos: público. Rate limit: 60/min.
  - Uso: el orquestador no rutea tráfico mientras devuelva 503.

## /v1/auth

JSON-only (sin OAuth2 form / `python-multipart`). Contrato + decisiones de
seguridad en el docstring de [`../app/api/v1/auth.py`](../app/api/v1/auth.py).

- **POST** `/v1/auth/register` — crea un usuario con email + password.
  - Request: `RegisterRequest = { email: EmailStr, password: string (8..128), display_name?: string (<=40) }`.
    `extra: forbid` (campos como `is_ephemeral` / `retention_sensitive_days` NO
    son seteables desde el wire: no se reusa `UserCreate`, se evita el mass-assignment).
  - Response 201: `UserOut` (incluye `id` / `created_at` / `updated_at`; **nunca**
    `password_hash`). El `email` se persiste normalizado (`strip().lower()`).
  - Response 409: email ya registrado (`{ "detail": "email ya registrado" }`).
  - Response 422: validación (password corto, email malformado, etc.). El eco del
    `input` de campos sensibles (`password`) se scrubea (regla #4, handler en `main.py`).
  - El 409 **revela que el email existe**: es un trade-off de enumeración
    **consciente y aceptado** en on-prem / mono-tenant (el alternativo —aceptar
    siempre + mail de "ya tenés cuenta"— exige infra de mail que el MVP no tiene).
- **POST** `/v1/auth/token` — verifica credenciales y devuelve un access token JWT.
  - Request: `LoginRequest = { email: EmailStr, password: string }`. `password`
    **sin** `min/max_length` a propósito: un 422 por longitud sería un oráculo de
    formato; login solo distingue 200 / 401.
  - Response 200: `TokenOut = { access_token: string, token_type: "bearer" }`.
  - Response 401: credenciales inválidas. **MISMO** 401 (status + `detail` +
    `WWW-Authenticate: Bearer`) para email inexistente y para password incorrecto
    (anti-enumeración); además timing-safe (dummy hash en el camino "email
    inexistente"). **NUNCA** un 404.
- Permisos: **público** (estos endpoints son el punto de entrada de auth).
- **Rate limit: TODO** — deuda conocida. El MVP no agrega dependencias (sin
  `slowapi` / Redis), así que no hay rate-limit aplicativo todavía; mitigarlo
  (slowapi / WAF / reverse-proxy) es trabajo posterior.
- `/v1/auth/refresh` y `/v1/auth/logout` quedan **diferidos**: el JWT es stateless
  y no hay store de revocación, así que el logout sería un no-op honesto y la
  única ventana de revocación es el TTL del access token. Se implementan cuando
  haya refresh tokens / blacklist, no como mentiras.

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

## /v1/sessions

Ciclo de vida de la `ChatSession`. Contrato + decisiones en el docstring de
[`../app/api/v1/sessions.py`](../app/api/v1/sessions.py).

- **POST** `/v1/sessions/{session_id}/close` — cierra una sesión seteando `ended_at`.
  - Path param: `session_id: UUID` (la sesión a cerrar).
  - Request: ninguno (el `user_id` sale del JWT, no del body).
  - Response 200: `SessionOut = { id, user_id, mode, started_at, ended_at, created_at, updated_at }`
    (mirror del modelo; `ended_at` queda **no nulo** tras el cierre). Nunca expone
    nada sensible.
  - **Idempotente**: cerrar una sesión ya cerrada devuelve **200** con el `ended_at`
    **original** (no se re-setea; cerrar dos veces es inocuo, **no** 409).
  - Response 404: sesión inexistente **o** de otro usuario — **mismo** 404 (status +
    `detail: "sesion no encontrada"`), **sin oráculo** de existencia ajena
    (aislamiento por `user_id` del JWT, igual que `resolve_chat_session`).
  - Response 401: sin token / token inválido (`get_current_user`).
  - Solo setea `ended_at`: **no** toca memoria, **no** encola consolidación (la
    consolidación episódica es M10 Ola 4).
- Permisos: **usuario autenticado** (solo sobre sus propias sesiones).
- Rate limit: TODO.
- Modos: todos.

---

Toda ruta nueva agrega entrada acá en el mismo PR.
