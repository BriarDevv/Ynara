# Respuestas al §7.1 — Contrato de `/v1/chat` (frontend ↔ backend)

> **Resumen.** Responde las preguntas abiertas del plan de integración del
> chat. Las 4 primeras son del **contrato del backend** (las contesto desde la
> capa LLM, que es lo que se construyó: `app/llm/`): streaming en un endpoint
> aparte, evento terminal `done` con `session_id` + `actions`, `actions[]` con
> `result`, y corregir `actions?` → `actions: Action[]`. Las 2 últimas son
> **decisiones de producto** (del owner): recomiendo markdown con subset seguro
> y un límite de ~4.000 chars, ambas con su fundamento. Nada de esto está
> cableado todavía (el router es M8, el endpoint es M9); este doc fija el
> **contrato objetivo** para esos milestones y corrige `ENDPOINTS.md` en lo que
> ya es claramente incorrecto.

Estado del backend hoy (para anclar las respuestas):

- `app/llm/schemas.py` ya define `ChatRequest` (`text`, `mode`, `session_id?`)
  y `ChatResponse` (`text`, `actions: list = []`, `session_id`).
- `app/llm/router.py` y el endpoint **no existen aún** (`NotImplementedError`).
  El cliente vLLM (`VllmClient`) ya hace streaming SSE y emite `CompletionChunk`
  (`delta_text`, `tool_call_delta`, `finish_reason`).
- `ynara.config.json[llm.serving].max_model_len`: Gemma **4096**, Qwen 32768.

---

## Backend (para @BriarDevv / la capa LLM)

### 1. Streaming: ¿SSE sobre `/v1/chat` por content-negotiation, o endpoint aparte?

**Endpoint aparte: `POST /v1/chat/stream` (SSE), y `POST /v1/chat` queda
no-streaming (JSON).**

Por qué:

- **Semánticas distintas.** El no-streaming devuelve un `ChatResponse` JSON
  completo (con `actions` ya ejecutadas). El streaming tiene otro contrato:
  tokens incrementales + un evento terminal, y **sin fallback mid-stream** (el
  `ResilientClient` de M3 sólo hace fallback on-prem en `complete()`, no en
  `stream()` — está documentado). Meter dos contratos tan distintos bajo un
  mismo path por `Accept:` los acopla y complica el testeo y la doc.
- **Claridad para el cliente.** Una ruta `/v1/chat/stream` es explícita y
  autodocumentada; el front elige stream o no por URL, no por header.
- **FastAPI.** `StreamingResponse` con `media_type="text/event-stream"` mapea
  directo; el endpoint sólo re-emite los `CompletionChunk` del cliente como SSE.

> Content-negotiation (`Accept: text/event-stream` sobre `/v1/chat`) es válido y
> lo usan algunos; lo descarto por el acople de semánticas, no por imposibilidad.

### 2. ¿Shape del evento terminal del stream que carga `session_id` + `actions`?

Correcto: `CompletionChunk` sólo trae `delta_text` / `tool_call_delta` /
`finish_reason` — **no** `session_id` ni `actions` (esos recién existen cuando
termina el turno entero, incluido el tool loop). El stream usa **eventos SSE con
nombre**:

```text
event: token
data: {"delta": "Hola"}

event: token
data: {"delta": " mundo"}

event: done
data: {"session_id": "0193...", "actions": [ ... ], "finish_reason": "stop"}
```

- `token` — un fragmento de texto (`delta`). El front concatena para mostrar.
- `done` — **evento terminal**: `{ session_id, actions, finish_reason }`. Es el
  análogo del `ChatResponse` no-streaming (el `text` el front ya lo acumuló de
  los `token`).
- `error` — si algo revienta mid-stream (sin fallback en M3): `{ code, message }`
  sin datos de usuario (regla #4). El caso normal de infra caída se sirve como
  respuesta **degradada** (texto degradado por `token` + `done`), no como error.

> Esto se modela con un `ChatStreamEvent` (union discriminada) o, más simple, con
> el campo `event:` de SSE como discriminador. Recomiendo SSE con `event:`.

### 3. ¿`actions[]` con `result`, o sólo `ToolCall` (`{id, name, arguments}`)?

**Con `result`.** Un item de `actions` es:

```jsonc
{
  "id": "call_abc",
  "name": "calendar.create_event",
  "arguments": { "title": "...", "start": "...", "end": "..." },
  "result": { "status": "ok", "event_id": "..." }   // o { "error": { "code", "message" } }
}
```

Por qué con `result`:

- El front quiere **renderizar lo que pasó** (chip "evento agendado", card de
  recordatorio), no sólo lo que se pidió. Para eso necesita el **resultado
  ejecutado**, no el `ToolCall` crudo.
- El `result` es el dict estructurado que devuelve el `ToolRegistry.execute`
  (hoy stub `{status: "not_wired", ...}`; el real cuando se cableen las tools), o
  `{ "error": { code, message } }` si la tool falló (nunca un traceback — regla
  del repo).
- `actions` refleja lo que **ejecutó el agente Qwen** en el tool loop (M8). Los
  modos Gemma no ejecutan tools → `actions: []`.

Concretamente: formalizar un schema `Action = { id, name, arguments, result }`
(hoy `ChatResponse.actions` es `list[dict[str, Any]]`, suficientemente laxo;
conviene tiparlo en M8/M9).

### 4. `ENDPOINTS.md` dice `actions?` pero el Pydantic es `actions = []`. ¿Corregimos?

**Sí.** `ChatResponse.actions: list[dict] = []` significa **siempre presente**
(lista vacía cuando no hubo acciones), nunca ausente. `actions?` (opcional) es
engañoso para el front. El contrato correcto es **`actions: Action[]`** (siempre
presente, posiblemente vacío). **Ya lo corregí en `ENDPOINTS.md`** en este mismo
PR.

---

## Producto (decisión del owner — recomiendo, vos decidís)

### 1. ¿El chat renderiza markdown?

**Recomiendo sí, un subset seguro desde el MVP** (bold, listas, inline code,
code blocks, links), sanitizado.

Por qué:

- Los modelos **ya producen markdown** naturalmente: el modo **Estudio**
  (explicaciones, tutoría) tira listas y bloques de código; Qwen estructura con
  bullets. En texto plano, `**negrita**` y ` ```código``` ` se ven literales y
  feos.
- **Seguridad**: renderizar markdown **sin HTML crudo** (ej. `react-markdown` +
  `rehype-sanitize`), links con `rel="noopener"`. Nada de `dangerouslySet...`.
- Los prompts dicen "sin emojis" pero **no** prohíben markdown; Estudio incluso
  pide "anclaje + ejemplo" (que suele querer código/listas).

> Si producto prefiere shippear más rápido con texto plano y markdown como
> fast-follow, es aceptable — pero sabiendo que el output va a verse rústico
> desde el día 1 porque los prompts ya generan markdown.

### 2. ¿Máximo de longitud del mensaje del usuario?

**Recomiendo ~4.000 caracteres**, alineado al plan, y **enforced en el backend**
(`ChatRequest.text` con `Field(max_length=4000)` → 422 si se pasa).

Fundamento (no es arbitrario):

- El mensaje del usuario **comparte ventana de contexto** con el system prompt
  (~700-900 tokens), el contexto de memoria recuperado (top-k) y el historial.
- El modelo más chico es **Gemma con `max_model_len = 4096` tokens**. ~4.000
  chars en español ≈ ~1.100-1.400 tokens (≈3 chars/token). Eso deja lugar para
  prompt + memoria + historia sin desbordar 4096.
- Un límite más alto (8k) sería viable en Qwen (32768) pero rompería en los
  modos Gemma. ~4.000 chars es el **techo seguro cross-modelo**.

> Decisión de producto, pero el ~4.000 del plan está bien fundado contra el
> `max_model_len` de Gemma. Si en producto se quiere más, hay que subir el
> `max_model_len` de Gemma (ADR-009 D3, valores provisionales) y medir VRAM.

---

## Acciones concretas que se derivan

| # | Acción | Dónde | Cuándo |
|---|--------|-------|--------|
| 1 | `actions?` → `actions: Action[]` + shape de `Action` + `/v1/chat/stream` | `ENDPOINTS.md` | **hecho en este PR** |
| 2 | Tipar `Action = {id, name, arguments, result}` (hoy `list[dict]`) | `app/llm/schemas.py` | M8/M9 |
| 3 | `ChatRequest.text` con `max_length=4000` (si producto confirma) | `app/llm/schemas.py` | M9 |
| 4 | Endpoints `POST /v1/chat` (JSON) + `POST /v1/chat/stream` (SSE eventos `token`/`done`/`error`) | `app/api/v1/chat.py` (nuevo) | M9 |
| 5 | Confirmar markdown sí/no + límite de chars | owner | antes de M9 |

Ver [`LLM-INFERENCE-INTEGRATION.md`](./LLM-INFERENCE-INTEGRATION.md) (M8 router + tool loop, M9 endpoint) y [`apps/backend/docs/ENDPOINTS.md`](../../apps/backend/docs/ENDPOINTS.md).
