# ENDPOINTS.md — Catálogo de endpoints

> Por cada endpoint: método+path, descripción, request schema,
> response schema, permisos, rate limit, modo que lo usa.

## /v1/health

- **GET** `/v1/health` — **liveness**: el proceso está vivo. No toca dependencias.
  - Request: ninguno.
  - Response: `{ "status": "ok", "version": "0.1.0" }` (siempre 200 si responde).
  - Permisos: público. Sin throttling aplicativo (no hay rate-limit por minuto).
- **GET** `/v1/health/ready` — **readiness**: pinga DB y Redis.
  - Request: ninguno.
  - Response 200: `{ "status": "ready", "version": "0.1.0", "checks": { "database": { "ok": true }, "redis": { "ok": true } } }`.
  - Response 503 (degraded): mismo shape, `status: "degraded"` y la dependencia caída con `{ "ok": false, "error": "<ClaseDeExcepción>" }`. El error es **solo el nombre de la clase**, nunca el connection string (regla #2 / #4).
  - Permisos: público. Sin throttling aplicativo (no hay rate-limit por minuto).
  - Uso: el orquestador no rutea tráfico mientras devuelva 503.

## /v1/modes

- **GET** `/v1/modes` — catálogo de modos declarados en `ynara.config.json[modes]`.
  - Request: ninguno.
  - Response 200: `{ "modes": [ { "id": "productividad", "model": "qwen-3.5-9b", "memory_layers": ["semantic", "episodic"], "tools_enabled": ["calendar", "reminder", "memory"], "tone": "neutro-eficaz" }, … ] }`. Los modos vienen en **orden de declaración** de la config (el orden del Mode Switcher). `id` es uno de `productividad | estudio | bienestar | vida | memoria`.
  - Permisos: **público** (mismo tier que `/health`). Es metadata de producto, no datos de usuario; los mismos campos ya viajan en el bundle del front. Sin rate-limit.
  - Uso: fuente **server-driven** del Mode Switcher del front (cambiar los modos no requiere rebuild). El front mapea cada `id` a su label/gradiente local.

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
  - Response 200: `TokenOut = { access_token: string, token_type: "bearer", refresh_token: string }`.
    En `/token` (y en `/refresh`) el `refresh_token` **siempre** viene poblado.
  - Response 401: credenciales inválidas. **MISMO** 401 (status + `detail` +
    `WWW-Authenticate: Bearer`) para email inexistente y para password incorrecto
    (anti-enumeración); además timing-safe (dummy hash en el camino "email
    inexistente"). **NUNCA** un 404.
- **GET** `/v1/auth/me` — devuelve la identidad autenticada.
  - Request: ninguno (el `user_id` sale del JWT, `CurrentUser`).
  - Response 200: `UserOut` (incluye `id` / `email` / `display_name` /
    timestamps; **nunca** `password_hash` — no es campo del schema).
  - Response 401: sin token / token inválido / expirado (`get_current_user`); **y
    también** si el `sub` del token (válido) ya no tiene fila (user borrado, caso
    raro): es la **propia identidad** caduca, así que 401 con `WWW-Authenticate:
    Bearer` (re-autenticarse), **no** un 404. El aislamiento "ajena == inexistente
    → 404 sin oráculo" aplica a recursos de **otros** users, no a la identidad propia.
  - Permisos: **usuario autenticado** (su propia identidad).
- **POST** `/v1/auth/refresh` — rota el refresh token y emite un par nuevo.
  - Request: `{ refresh_token: string }`.
  - Response 200: `TokenOut = { access_token, token_type: "bearer", refresh_token }`
    (par nuevo; el `refresh_token` siempre viene poblado).
  - **Rotación single-use con reuse-detection a nivel familia (claim `sid`)** —
    el handler tiene 4 ramas:
    0. El `sid` del refresh ya pertenece a una familia revocada → **401**.
    1. **first-use**: el gate atómico `revoke_if_absent` (SET NX EX) gana el
       claim → mintea un par nuevo (propaga el mismo `sid`) + setea un **grace
       marker** apuntando al `jti` del sucesor → **200**.
    2. **benign-retry** (dentro del grace `AUTH_REFRESH_REUSE_GRACE_SECONDS`,
       default 30s): el refresh ya rotado reaparece pero existe el grace marker
       → re-emite convergiendo en el **sucesor canónico** (**200**, idempotente);
       NO revoca la familia.
    3. **breach** (reuse fuera del grace): no hay grace marker → revoca la
       **familia entera** (`revoke_family(sid)`, TTL = vida completa del refresh)
       → **401**.
  - Response 401: token inválido, no es `type=refresh`, expirado, **o** reuse
    fuera del grace (breach) que revoca la familia entera vía `sid` (ramas 0 y 3).
  - Permisos: **público** (el propio refresh token es la credencial).
- **POST** `/v1/auth/logout` — revoca la sesión activa (blocklist Redis).
  - Request: `{ refresh_token?: string }` (opcional) + `Authorization: Bearer <access>`.
  - Requiere un access token válido. Si el access trae `sid`, revoca la
    **familia entera** (`revoke_family(sid)`, TTL = vida completa del refresh):
    el refresh y **todos los access hermanos** de esa sesión quedan inválidos;
    otras sesiones (distinto `sid`) no se afectan. Además blocklistea el `jti`
    del access (y el del `refresh_token` si viene en el body) en Redis con TTL =
    vida restante del token (self-expire) — los `revoke` por `jti` individual
    quedan como compat para tokens pre-#142 sin `sid`. Un token blocklisteado o
    de una familia revocada da 401 en `get_current_user`.
  - Response **204** No Content (sin body). **Best-effort / idempotente**: llamar
    logout dos veces es inocuo.
  - **fail-open**: si Redis está caído, la revocación se desactiva (degrada al
    baseline JWT-stateless); el token vale hasta su `exp`.
  - Permisos: **usuario autenticado**.
- Permisos: `register` / `token` / `refresh` son **público** (punto de entrada de
  auth); `me` y `logout` requieren token.
- **Rate limit** — implementado en `app/core/ratelimit.py`, estado en Redis:
  - `POST /auth/token`: lockout por `(ip, sha256(email)[:32])` tras
    `AUTH_LOGIN_MAX_ATTEMPTS` (5) intentos en `AUTH_LOGIN_WINDOW_SECONDS` (900s),
    lockout `AUTH_LOGIN_LOCKOUT_SECONDS` (900s). El email **nunca** va crudo en
    las keys (se hashea). Anti-enumeración: el 429 llega al mismo nº de intentos
    exista o no el email.
  - `POST /auth/register`: por IP (`AUTH_REGISTER_MAX_ATTEMPTS` 10,
    `AUTH_REGISTER_WINDOW_SECONDS` 3600s).
  - `POST /auth/refresh`: por `(ip, sub)` (`AUTH_REFRESH_MAX_ATTEMPTS` 30,
    `AUTH_REFRESH_WINDOW_SECONDS` 900s) — más permisivo que el login (rotación
    legítima frecuente). El 429 va DESPUÉS de validar firma + `sub`, así no
    introduce oráculo.
  - Al pasar el umbral responde **429** con header `Retry-After`.
  - **fail-open**: si Redis cae, el rate-limit se desactiva (auth sigue
    funcionando, sin throttling aplicativo).

## /v1/users

- **PATCH** `/v1/users/me` — update parcial del perfil propio.
  - Request: `UserUpdate = { display_name?: string (<=40), onboarding_completed?: bool, retention_sensitive_days?: int (30..365) }`. Solo se aplican los campos **enviados con valor no nulo** (`exclude_none`); un PATCH sin campos es un no-op idempotente, y no se puede pisar con `null` un campo NOT NULL.
  - Response 200: `UserOut` (incluye `id` / `email` / `display_name` / `onboarding_completed` / `retention_sensitive_days` / timestamps; **nunca** `password_hash`).
  - Response 401: sin token / token inválido / expirado, **o** el `sub` válido ya no tiene fila (identidad propia caduca, mismo criterio que `/v1/auth/me`; **nunca** 404).
  - Response 422: `retention_sensitive_days` fuera de `30..365`, o `display_name` > 40.
  - Permisos: **usuario autenticado** (su propio perfil). Tabla `users` (operativa, **no** sagrada); sin migración (columnas existentes).

## /v1/chat

Dos endpoints: uno no-streaming (JSON) y uno SSE. Contrato + justificación en
[`../../../docs/planning/RESPUESTAS-CONTRATO-CHAT.md`](../../../docs/planning/RESPUESTAS-CONTRATO-CHAT.md).

- **POST** `/v1/chat` (no-streaming):
  - Request: `{ text: string (límite ~4000 chars), mode: Mode, session_id?: UUID }`
  - Response: `{ text: string, actions: Action[], session_id: UUID, finish_reason: string | null }`
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
- Rate limit: por `user_id` (del JWT), `CHAT_MAX_REQUESTS` (60) por `CHAT_WINDOW_SECONDS` (60s); 429 con `Retry-After` al cruzar el techo. fail-open si Redis cae. Aplica a `/chat` y `/chat/stream`.
- Modos: todos.

## /v1/memory

Superficie **privacy-first** donde el **dueño** ve, exporta y borra su propia
memoria con su JWT. **Ola 1** (los 3 GET: list/detail/export) + **Ola 2**
(PATCH/DELETE individual) + **Ola 3** (wipe total con dry-run + confirm). Contrato
+ decisiones en el docstring de [`../app/api/v1/memory.py`](../app/api/v1/memory.py).

Invariantes (regla #3 / ADR-007 / ADR-010):

- **Aislamiento**: todo query filtra por el `user_id` del JWT (ligado en el
  `__init__` del store). Una ref de otro usuario da el **mismo** 404 que una
  inexistente (sin oráculo de existencia ajena).
- **Decrypt post-ownership**: `get_by_id` (semantic/episodic) filtra por
  `id` + `user_id` y retorna `None` **antes** de tocar crypto si la fila no es del
  user; nunca se intenta descifrar el blob de otro usuario.
- El **blob cifrado crudo nunca viaja**: los `*Out` exponen `content` / `summary`
  en **plaintext** (descifrados en el store).

- **GET** `/v1/memory` — lista la memoria del usuario, opcionalmente por capa.
  - Query: `layer?: {semantic, episodic, procedural}`, `limit?: int (1..100, default 50)`,
    `offset?: int (>=0, default 0)`.
  - Response 200 **sin** `layer`: agrupado por capa —
    `{ "semantic": { "items": SemanticMemoryOut[], "total": N }, "episodic": {...}, "procedural": {...} }`.
    `total` es el conteo completo del user en esa capa; `items` es la página
    `limit`/`offset`.
  - Response 200 **con** `?layer=<capa>`: solo la `*Page` de esa rama
    (`{ "items": [...], "total": N }`).
  - Response 422: `limit` fuera de `[1, 100]`, `offset < 0`, o `layer` inválida.
  - `content` / `summary` van descifrados; el embedding no se expone.
- **GET** `/v1/memory/search?q=` — búsqueda semántica en hechos + momentos.
  - Query: `q: string (1..200)` (requerida). Vacía tras `strip` → 200 con `total: 0`.
  - Response 200: `{ "query": string, "total": N, "results": MemorySearchHit[] }` donde
    `MemorySearchHit = { layer, ref, snippet, score (0..1), occurred_at }`. Orden:
    `semantic` (hechos) primero, luego `episodic` (momentos); `score` es un **proxy por
    rank** decreciente (el store no expone el score crudo del reranker y su firma
    sagrada no se toca, regla #3). `procedural` **no** entra (key-value, sin búsqueda
    semántica).
  - Response 422: `q` ausente o fuera de `1..200`.
  - Permisos: **usuario autenticado** (su propia memoria; los stores filtran por
    `user_id`). El `snippet` va descifrado (regla #4); el blob cifrado nunca viaja. Sin
    migración; **no** toca `app/memory/` (solo llama a `search`, read).
- **GET** `/v1/memory/{layer}/{ref}` — detalle de **un** ítem por capa + referencia.
  - Path: `layer: {semantic, episodic, procedural}`; `ref: UUID` para
    semantic/episodic, `key (str)` para procedural.
  - Response 200: el `*Out` de la capa (`SemanticMemoryOut` / `EpisodicMemoryOut` /
    `ProceduralMemoryOut`) con el contenido descifrado + metadata.
  - Response 404: ref inexistente **o** de otro usuario — **mismo** 404 (status +
    `detail: "memoria no encontrada"`), sin oráculo de existencia ajena.
  - Response 422: `layer` inválida, o `ref` no-UUID en semantic/episodic.
- **GET** `/v1/memory/export` — export JSON versionado de las 3 capas completas.
  - Request: ninguno.
  - Response 200: `{ "version": 1, "exported_at": <iso>, "semantic": SemanticMemoryOut[],
    "episodic": EpisodicMemoryOut[], "procedural": ProceduralMemoryOut[] }` (las 3
    capas **completas**, sin paginar, descifradas). Header
    `Content-Disposition: attachment; filename="ynara-memory-export.json"`.
- **PATCH** `/v1/memory/{layer}/{ref}` — edita **un** ítem de memoria del usuario.
  - Path: `layer: {semantic, episodic, procedural}`; `ref: UUID` para
    semantic/episodic, `key (str)` para procedural.
  - Body (`MemoryPatchRequest`, polimórfico por capa, **no sagrado**): `content?:
    str (1..4096)` para semantic, `value?: object (JSONB)` para procedural. El
    endpoint valida la correspondencia body↔capa.
  - `semantic`: actualiza el `content` (re-embeddea + re-cifra) → 200
    `SemanticMemoryOut`.
  - `procedural`: reemplaza el `value` de una **key existente** (UPDATE puro, **no**
    upsert; **no** resetea el decay — editar a mano no es reforzar, ADR-007 D1) →
    200 `ProceduralMemoryOut`. Si la key no existe → 404 (jamás crea vía PATCH).
  - `episodic`: **405** Method Not Allowed — el `summary` lo genera el worker de
    consolidación; se **borra** (DELETE) o se regenera, no se reescribe a mano.
  - Response 404: ref inexistente **o** de otro usuario — **mismo** 404
    (`detail: "memoria no encontrada"`), sin oráculo ni mutar/descifrar data ajena.
  - Response 422: `layer` inválida, `ref` no-UUID (semantic/episodic), body que no
    aplica a la capa (semantic sin `content`, procedural sin `value`), o `content`
    vacío / >4096.
  - **Audit (issue #161)**: tras un UPDATE efectivo (semantic/procedural), antes del
    commit, escribe una fila en `audit_log` (`operation=UPDATE`, `target_layer`,
    `target_id`, `record_hash` = SHA-256 del nuevo `content`/`value` canónico;
    `sensitive=false`, `origin_*=None`) en la **misma** transacción que el update.
- **DELETE** `/v1/memory/{layer}/{ref}` — borra **un** ítem de memoria del usuario.
  - Path: igual que PATCH (`layer` + `ref` UUID|key). Aplica a las **3** capas
    (incluida episodic: el dueño sí puede borrar un episodio, aunque no editarlo).
  - Response **204** No Content (sin body) en éxito; el blob cifrado nunca viaja.
  - **Audit (issue #161)**: tras un DELETE efectivo, antes del commit, escribe una fila
    en `audit_log` (`operation=DELETE`, `target_layer`, `target_id`, `record_hash` =
    SHA-256 de la ref/key; `sensitive=true` **solo** para episodic, `origin_*=None`) en
    la **misma** transacción que el borrado.
  - Response 404: ref inexistente **o** de otro usuario — **mismo** 404
    (`detail: "memoria no encontrada"`), sin oráculo ni tocar data ajena.
  - Response 422: `ref` no-UUID en semantic/episodic.
- **POST** `/v1/memory/wipe?dry_run=true` — **dry-run** (preview) del wipe total:
  conteos por capa de lo que se borraría. **Read-only** (no muta, no commitea, no
  descifra). El body se ignora.
  - El preview va en **POST** (no GET) **a propósito**: `/memory/wipe` es la
    superficie de una operación **destructiva**, y un GET debe ser seguro/idempotente
    — un prefetch / crawler que dispare un GET no debe tocarla ni para previsualizar.
    El preview es read-only igual, pero se mueve al verbo no-seguro para que **nunca**
    lo gatille una navegación accidental. El shape es idéntico al del viejo GET.
  - Request: `?dry_run=true` (query); body ninguno.
  - Response 200: `MemoryWipePreview = { "semantic": N, "episodic": N,
    "procedural": N, "total": N }` (`total` = suma de las 3 capas). **Solo
    enteros** (regla #4): nunca `content` / `summary`.
  - **Siempre 200**, incluso todo en 0 (un user sin memoria es estado válido;
    **jamás 404**). El cliente usa estos conteos como los `expected_*` del execute.
- **POST** `/v1/memory/wipe` (sin `dry_run` / `dry_run=false`) — **ejecuta** el wipe
  TOTAL de las 3 capas — **DESTRUCTIVO e irreversible** (hard-delete físico).
  Operación SAGRADA (regla #3).
  - Body (`MemoryWipeConfirm`, **no sagrado**, **obligatorio** en el execute):
    `{ "expected_semantic": int>=0, "expected_episodic": int>=0,
    "expected_procedural": int>=0 }` — los conteos per-capa que el cliente vio en el
    preview fresco (guarda de intención). **Sin body y sin `dry_run` → 422** (el
    execute exige el confirm; para solo previsualizar usá `?dry_run=true`).
  - El endpoint **reconcuenta** las 3 capas y compara con los `expected_*`:
    - **Coinciden** → `wipe()` de las 3 capas + `commit` (recount+wipe+commit en la
      **misma** transacción) → Response 200 `MemoryWipeResult = { "semantic": N,
      "episodic": N, "procedural": N, "total": N }` con los **rowcounts REALES**
      borrados (pueden diferir del preview si el worker insertó en el ínterin; ese
      número siempre es verdad). **Solo enteros** (regla #4). **Audit (issue #161)**:
      por cada capa con rowcount > 0 escribe una fila en `audit_log`
      (`operation=DELETE`, `target_id=None`, `record_hash` = SHA-256 de `wipe:<capa>`;
      episodic `sensitive=true` conservador, semantic/procedural `sensitive=false`), en
      la misma transacción que el wipe.
    - **No coinciden** → Response **409** Conflict con los **conteos ACTUALES** en el
      `detail` (para re-confirmar con un preview fresco); **nada** se borra ni
      commitea. `detail = { "message": str, "semantic": N, "episodic": N,
      "procedural": N, "total": N }` (solo enteros + el message).
  - **Idempotente**: wipe de user vacío con confirm `{0,0,0}` → 200 `{0,0,0,0}`; un
    segundo wipe seguido (preview `{0,0,0}`, confirm `{0,0,0}`) → 200 `{0,0,0,0}`.
    **Jamás 404**. Un confirm viejo `{N,..}` tras ya haber wipeado → **409**
    (anti-doble-click).
  - Response 422: body ausente (sin `dry_run`), o mal formado (campo faltante,
    negativo, o uno de más — `extra=forbid`).
  - **TOCTOU / atomicidad**: el recount y el wipe van en la **misma** transacción
    del request; el confirm es una guarda de INTENCIÓN (prueba que el humano vio el
    plan), no cirugía exacta. El `DELETE WHERE user_id` barre el estado presente
    completo; el receipt reporta el rowcount real. No descifra ni logea contenido.
- Response 401 (todos): sin token / token inválido (`get_current_user`).
- Permisos: **usuario autenticado**, solo su propia memoria.
- Rate limit: dos endpoints están limitados, ambos por `user_id`, con 429 +
  `Retry-After` al cruzar el techo y **fail-open** si Redis cae:
  - `GET /v1/memory/export` (el endpoint más caro): `MEMORY_EXPORT_MAX_REQUESTS` (5)
    por `MEMORY_EXPORT_WINDOW_SECONDS` (3600s).
  - `POST /v1/memory/wipe` **execute** (la operación destructiva): `MEMORY_WIPE_MAX_REQUESTS`
    (5) por `MEMORY_WIPE_WINDOW_SECONDS` (3600s), vía `check_memory_wipe_rate_limit`
    (`memory.py`). Solo gatea el **execute**: el preview `?dry_run=true` es read-only y
    **NO** consume cuota. El check corre **antes** de tocar la DB.
  - El resto de `/v1/memory` (list/detail, PATCH/DELETE individual) no tiene rate-limit
    aplicativo.

## /v1/sessions

Read surfaces + ciclo de vida de la `ChatSession`. Contrato + decisiones en el
docstring de [`../app/api/v1/sessions.py`](../app/api/v1/sessions.py).

Invariante transversal — **aislamiento por `user_id` del JWT**: el listado trae
solo las sesiones del user, y un detail de sesión ajena da el **mismo** 404 que
una inexistente (sin oráculo de existencia ajena). Todas las read surfaces son
**solo lectura** (ningún GET muta ni encola nada).

- **GET** `/v1/sessions` — lista paginada de las sesiones del usuario.
  - Query: `limit?: int (1..100, default 50)`, `offset?: int (>=0, default 0)`.
  - Response 200: `SessionListPage = { "items": SessionOut[], "total": N }`.
    `items` es la página `limit`/`offset` ordenada por `started_at` **DESC** (la
    más reciente primero); `total` es el conteo **completo** de sesiones del user
    (no el largo de la página), para paginar. `SessionListPage` vive en
    `app/schemas/session_api.py` (no sagrado, espeja `memory_api.py`).
  - Response 422: `limit` fuera de `[1, 100]` o `offset < 0`.
  - **Aislamiento**: `WHERE user_id == current` en el SELECT y en el COUNT — solo
    las sesiones del user; nunca aparecen sesiones ajenas.
- **GET** `/v1/sessions/{session_id}` — detalle de **una** sesión del usuario.
  - Path param: `session_id: UUID`.
  - Response 200: `SessionOut` (mirror del modelo; nunca nada sensible).
  - Response 404: sesión inexistente **o** de otro usuario — **mismo** 404 (status +
    `detail: "sesion no encontrada"`), **sin oráculo** de existencia ajena (idéntico
    al `close`).
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
  - Solo setea `ended_at`: **no** toca memoria. En el **primer cierre real**
    (la sesión todavía no estaba cerrada), tras el commit encola
    `consolidate_session.delay()` (consolidación episódica) best-effort
    fail-open: si el broker está caído el close devuelve 200 igual. Un segundo
    cierre (idempotente) **no** re-encola.
- Response 401 (todas las rutas): sin token / token inválido (`get_current_user`).
- Response 429 (todas las rutas): supera el rate-limit por `user_id` —
  `detail: "demasiados intentos, intente mas tarde"` (neutro) + header
  `Retry-After` == `SESSIONS_WINDOW_SECONDS`.
- Permisos: **usuario autenticado** (solo sobre sus propias sesiones).
- Rate limit: por `user_id` (del JWT), **un solo bucket** compartido por las 3 rutas
  (`list`/`get`/`close`), `SESSIONS_MAX_REQUESTS` (120) por `SESSIONS_WINDOW_SECONDS`
  (60s); 429 con `Retry-After` al cruzar el techo. fail-open si Redis cae (sin freno,
  baseline). El check corre **antes** de tocar la DB.
- Modos: todos.

## /v1/admin

Panel admin interno: 6 GET de **métricas read-only** del dashboard. Contrato +
decisiones en el docstring de [`../app/api/v1/admin.py`](../app/api/v1/admin.py).

Invariantes transversales:

- **Gate de admin** (`get_current_admin`, `app/core/deps.py`): firma/exp/type/blocklist
  del JWT + flag `users.is_admin` **o** bootstrap (`str(user_id) in
  ADMIN_BOOTSTRAP_IDS`). Sin admin → **401 estático** (mismo `detail` que credenciales
  inválidas; sin oráculo de "existe pero no es admin", regla #4).
- **Solo lectura**: ningún endpoint muta ni encola; todo es COUNT/GROUP BY on-the-fly
  (sin agregados precalculados). No hay rate-limit aplicativo (acceso de operador).
- **Privacidad (regla #4)**: NUNCA se descifra contenido de memoria; el audit del panel
  NUNCA expone `record_hash` ni `target_id` (ausentes del SELECT y del schema). Los UUID
  que viajan (id de audit / episodic) son opacos, sin email ni PII.
- **Query `range`** ∈ `{24h, 7d, 30d, 90d}` (default `7d`) en los 5 endpoints de
  métricas; `/admin/system` **no** toma rango (runtime/config). Fuera de rango → 422.
- **Honestidad de dato** (gaps del schema): DAU/WAU/MAU son **aproximados** por sesiones
  (`is_approximate=true`; no hay `last_seen`); la conversión efímero→registrado es
  **estimada** (`is_estimate=true`; no hay timestamp de conversión); la duración por modo
  cuenta solo sesiones cerradas.

- **GET** `/v1/admin/overview?range=7d` — KPIs + serie de sesiones + mix de modos + preview de audit.
  - Response 200: `AdminOverviewOut = { perimeter{status, detail, checked_at}, kpis{users_total, sessions, memories, audit_events}, sessions_series: TimePoint[], mode_mix: {mode, value}[], audit_preview: {id, created_at, operation, target_layer, origin_mode, sensitive}[] }`. `memories` = suma de las 3 capas. El `audit_preview` **no** incluye `record_hash`/`target_id`.
- **GET** `/v1/admin/users?range=7d` — actividad aproximada, heatmap, conversión, signups.
  - Response 200: `AdminUsersOut = { activity{dau, wau, mau, is_approximate}, heatmap: {date, count, level}[], conversion{ephemeral, registered, conversion_pct, is_estimate}, signups: {date, count}[] }`. DAU/WAU/MAU = COUNT(DISTINCT user_id) sobre `sessions.started_at` por ventana (proxy).
- **GET** `/v1/admin/modes?range=7d` — mix de sesiones por modo + duración media por modo.
  - Response 200: `AdminModesOut = { total, mix: {mode, sessions, pct}[], duration: {mode, avg_minutes, closed_sessions, open_sessions}[] }`. Duración = AVG(`ended_at - started_at`) solo sobre cerradas; abiertas contadas aparte.
- **GET** `/v1/admin/moat?range=7d` — conteos por capa + crecimiento + salud procedural + consolidación. **Cero descifrado**.
  - Response 200: `AdminMoatOut = { counts{semantic, episodic, procedural}, deltas{...}, growth: {key, points: TimePoint[]}[], procedural{stale_count, healthy_count, confidence_buckets: {range, count}[]}, consolidation{backlog, recent_episodic: {id, occurred_at, is_sensitive}[]} }`. `backlog` = sesiones cerradas sin episódica consolidada. `recent_episodic` es solo metadata (sin `summary`).
- **GET** `/v1/admin/audit?range=7d&operation=&target_layer=&origin_mode=&origin_model=&sensitive=&limit=50&offset=0` — página de audit filtrable.
  - Response 200: `AdminAuditPage = { items: AdminAuditRow[], total, sensitive_pct }` donde `AdminAuditRow = { id, created_at, operation, target_layer, origin_mode, origin_model, origin_tool, sensitive }`. **SIN `record_hash` ni `target_id`** (omitidos del SELECT y del schema, regla #4). `total` es el conteo completo que matchea los filtros; `sensitive_pct` el porcentaje sensible dentro del total filtrado. Orden `created_at` DESC, paginación `limit` (1..100, default 50) / `offset` (≥0). Fuera de rango → 422.
- **GET** `/v1/admin/system` — salud de infra + guard anti-prod + inventario de runtime. **Sin** `range`, sin queries de negocio.
  - Response 200: `AdminSystemOut = { guard{active, db_target, is_prod_in_dev}, services{postgres{up, latency_ms, detail, checked_at}, redis{...}}, runtime{models, modes, schema_head, embedder, reranker, build_version} }`. `db_target` es solo el **host** (nunca el connection string con credenciales, regla #2). Postgres = `SELECT 1`; Redis = `PING` al singleton `app.state.redis`; `schema_head` = head de Alembic.

### Playground admin (F1 ADR-018)

Inventario de serving read-only + chat de prueba aislado. **Sin** `range`. Contrato +
lógica del handler en el docstring de [`../app/api/v1/admin.py`](../app/api/v1/admin.py)
(sección "Playground admin"). Privacidad (regla #4): el serving **nunca** expone
`base_url` ni connection strings; el playground **no persiste nada** (sin `DbSession`) y
**nunca** ecoa el payload crudo de un `LlmError` (el `detail` del error es solo
`type(exc).__name__`).

- **GET** `/v1/admin/serving` — estado read-only del serving: config estática (`ynara.config.json` + settings) + salud runtime agregada (`await llm_client.health()`). **Sin** `range`.
  - Response 200: `ServingOut = { backend: "fake"|"vllm", is_real, serving_healthy, request_timeout_s, low_perf_available, models: ServingModelOut[], embedder, reranker }` donde `ServingModelOut = { key, served_name, role, writes_memory, context_window, max_model_len, quantization, tool_parser, healthy, default_thinking }`. **SIN `base_url` ni connection strings** (regla #4). Con `backend=fake`: `serving_healthy=true` (el Fake reporta sano) pero `is_real=false` y `low_perf_available=false` (la UI usa `is_real` para advertir "serving real no disponible"). `healthy` por modelo = `health().healthy` ∧ `serves_model(served_name)`. `default_thinking` = `false` conversational / `true` agent (gotcha Gemma+thinking, ADR-012 D4).
- **POST** `/v1/admin/playground` — completion ad-hoc **sync** contra un modelo elegido, llamando `llm_client.complete()` **directo** (sin `route()`/`run_tool_loop()`, sin `DbSession`): cero sesión/memoria/tools/consolidación. **Aislamiento total**.
  - Request: `PlaygroundIn = { model: string (served_name "gemma4"|"qwen"), mode?: string|null, message: string (1..4000), system_prompt?: string|null, params: PlaygroundParams, thinking?: bool|null }` donde `PlaygroundParams = { max_tokens: int (1..4096, default 1024), temperature: float (0..2, default 0.7), low_perf: bool (default false) }`. System prompt = `system_prompt` > `load_prompt(mode)` (si hay `mode`) > default neutro. `thinking` `null` → default por role (`false` conversational / `true` agent).
  - **Preset "bajo rendimiento"** (`params.low_perf=true`): pisa `max_tokens=min(256, …)`, `temperature=min(0.2, …)`, `thinking=false`, `timeout_s=30`. Es un preset **per-request** (no muta el serving global, F1 vs F2).
  - Response 200: `PlaygroundOut = { text, finish_reason, model_name, prompt_tokens, completion_tokens, latency_ms, thinking_used }`. `thinking_used` = el thinking efectivo aplicado (override/preset/default por role), para mostrar en la UI.
  - Response 422: `model` fuera del catálogo de served_names (`detail: "modelo no servido"`), `mode` desconocido (`detail: "modo desconocido"`), o validación del body (`message` vacío/>4000, params fuera de rango).
  - Response 409: backend fake (`detail: "serving real no disponible"`) — corta **antes** de llamar `complete()` para no reventar contra el Fake del lifespan (sin respuestas encoladas → `AssertionError`/500). El playground es útil solo con `LLM_BACKEND=vllm`.
  - Response 502/503/504: mapeo de la familia `LlmError` del cliente real, **sin ecoar el payload** (regla #4: `detail = type(exc).__name__`): `LlmTimeoutError`→504; `LlmUnavailableError`/`LlmOverloadedError`→503; `LlmContextOverflowError`/`LlmBadRequestError`/`ModelNotServedError`→422; genérico `LlmError`→502.
- Response 401 (todas las rutas): sin token / token inválido / user no admin.
- Permisos: **admin** (flag `is_admin` o `ADMIN_BOOTSTRAP_IDS`).

---

Toda ruta nueva agrega entrada acá en el mismo PR.
