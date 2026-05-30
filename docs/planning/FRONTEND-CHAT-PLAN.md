# Frontend · Chat / Conversación (modo) — Plan completo

> **Estado**: v1 — borrador para revisión
> **Fecha**: 2026-05-30
> **Owner**: @MateoGs013
> **Reviewers sugeridos**: @BriarDevv (contrato LLM / backend), @querques20 (UX / UI)
> **Alcance**: `apps/web` (mock-first con MSW). Mobile (Expo) y `packages/ui` quedan fuera.
> **Continúa**: [`archive/FRONTEND-ONBOARDING-PLAN.md`](./archive/FRONTEND-ONBOARDING-PLAN.md) (ejecutado).

---

## 0. Contexto

Este documento es el plan del **segundo slice navegable** del frontend web de Ynara: la **pantalla de conversación** (chat con el asistente, consciente del modo activo). El onboarding ya está mergeado y la home vacía ya **promete** el chat (el `ChatInputDocked` está deshabilitado con tooltip "Próximamente"). Este plan lo hace real.

**Enfoque: mock-first con MSW**, igual que el onboarding. El backend tiene la capa LLM como librería (clientes vLLM, streaming, tool-calls, routing por modo) pero **todavía no expone `POST /v1/chat` por HTTP** (es el milestone M9, pendiente) y **no tiene auth** (`core/security.py` en `NotImplementedError`). Por eso construimos contra mocks y nos conectamos al backend real cuando M9 + auth aterricen.

**La ventaja clave frente al onboarding**: el contrato del chat **ya existe en Pydantic** (`apps/backend/app/llm/schemas.py`: `ChatRequest` / `ChatResponse` / `ChatMessage` / `ToolCall` / `CompletionChunk`) y el endpoint está spec'eado en [`apps/backend/docs/ENDPOINTS.md`](../../apps/backend/docs/ENDPOINTS.md). O sea, a diferencia del contrato de auth (que sigue provisional), **el mock del chat puede espejar un Pydantic real** → la regla "Pydantic gana, Zod sigue" aplica desde el día 1 y la divergencia es detectable en code review.

### Por qué este plan existe ahora

- El onboarding dejó al usuario en una home que no hace nada todavía: el siguiente paso obvio es **hablar con Ynara**.
- El backend ya definió el contrato del router (`route(ChatRequest) -> ChatResponse`) y el formato de streaming (`CompletionChunk`, SSE estilo OpenAI). Construir el frontend contra ese contrato ahora minimiza retrabajo cuando M9 cierre.
- Es el core del producto: sin chat, Ynara es un onboarding lindo sin sustancia.

---

## Tabla de contenidos

1. [Qué heredamos](#1-qué-heredamos)
2. [El contrato del chat (mirror del backend)](#2-el-contrato-del-chat-mirror-del-backend)
3. [Chat — spec funcional](#3-chat--spec-funcional)
4. [Arquitectura técnica](#4-arquitectura-técnica)
5. [Plan de ejecución](#5-plan-de-ejecución)
6. [Definition of Done](#6-definition-of-done)
7. [Decisiones a validar, riesgos y landmines](#7-decisiones-a-validar-riesgos-y-landmines)
8. [Referencias cruzadas](#8-referencias-cruzadas)

---

## 1. Qué heredamos

Del slice de onboarding ya mergeado, reusamos sin reconstruir:

| Pieza | Dónde | Uso en el chat |
|---|---|---|
| Design system + tokens | `apps/web/src/app/globals.css` | Burbujas, tints por modo, motion |
| Tints por modo | `apps/web/src/components/ui/modes.ts` (`MODES`, `gradientClass`) | Acento de cada conversación según modo |
| `ModeChip` | `components/ui/ModeChip.tsx` | Header de la conversación + switcher |
| `ModeSwitcher` | `features/home/components/ModeSwitcher.tsx` | Cambiar de modo (= nueva sesión) |
| `ChatInputDocked` | `features/home/components/ChatInputDocked.tsx` | **Se evoluciona** a composer real |
| Fetcher tipado + `ApiError` | `lib/api.ts` | Requests al `/v1/chat` mock |
| Infra MSW + toggle | `lib/api.mocks.ts`, `lib/env.ts` (`shouldEnableMocks`) | Handlers del chat |
| `useUserStore` | `stores/user.ts` | `displayName`, `interestedModes`, `token` |
| `@ynara/shared-schemas` (Zod) | `packages/shared-schemas/` | Donde viven los Zod del chat |
| Stack de tests | vitest + RTL + playwright + axe | Misma red para el chat |

**Modos** (de [`ynara.config.json`](../../ynara.config.json), no hardcodear):

| Modo | Modelo | Rol | Tools | Memoria |
|---|---|---|---|---|
| productividad | qwen-3.5-9b | **agente** | calendar, reminder, memory | semantic + episodic |
| estudio | gemma-4-26b-a4b | conversacional | — | episodic + procedural |
| bienestar | gemma-4-26b-a4b | conversacional | — | procedural + semantic |
| vida | gemma-4-26b-a4b | conversacional | — | procedural |
| memoria | qwen-3.5-9b | **agente** | memory | las 3 capas |

> **Regla de oro del routing** (ADR-002): **Qwen** (productividad, memoria) ejecuta tools y escribe memoria → produce `actions[]`. **Gemma** (estudio, bienestar, vida) solo conversa y lee memoria → `actions[]` vacío. La UI tiene que reflejar esta diferencia.

> **Nota de fuente**: la tabla de routing de `AGENTS.md` lista `vida` con "calendar (read)", pero `ynara.config.json` (`tools_enabled: []`), `MODES.md` y ADR-002 coinciden en que **Gemma no llama tools**. Acá manda la config canónica: `vida` sin tools. Vale corregir el resumen de `AGENTS.md` en un PR aparte (queda como deuda, no parte de este plan).

---

## 2. El contrato del chat (mirror del backend)

Fuente de verdad: [`apps/backend/app/llm/schemas.py`](../../apps/backend/app/llm/schemas.py) (Pydantic) + [`apps/backend/docs/ENDPOINTS.md`](../../apps/backend/docs/ENDPOINTS.md) + las respuestas de contrato de @BriarDevv en [`RESPUESTAS-CONTRATO-CHAT.md`](./RESPUESTAS-CONTRATO-CHAT.md) (las preguntas de la §7.1 quedaron **cerradas** ahí). Los Zod de este plan son **mirror manual** — si el backend cambia, se corrige Zod en el mismo PR.

### 2.1 Endpoints

Son **dos** endpoints (decisión cerrada: el streaming va aparte, no por content-negotiation):

```
POST /v1/chat            (JSON, no-streaming)
  Request:  { text: string (≤ ~4000 chars), mode: Mode, session_id?: string }
  Response: { text: string, actions: Action[], session_id: string }

POST /v1/chat/stream     (SSE, text/event-stream)
  Request:  igual que /v1/chat
  Eventos:  event: token  data: { delta: string }
            event: done   data: { session_id, actions: Action[], finish_reason }
            event: error  data: { code, message }      // sin datos de usuario

  Auth:     usuario autenticado (hoy NO existe → mock no lo exige)
  Modos:    todos
```

> **Sin fallback mid-stream**: el `ResilientClient` (M3) solo hace fallback en `complete()`, no en `stream()`. La infra caída se sirve como **respuesta degradada** (texto degradado vía `token` + `done`), **no** como evento `error`.

### 2.2 Shapes a espejar en Zod (`packages/shared-schemas/src/chat.ts`)

```ts
// Mirror de app/llm/schemas.py — Pydantic gana, Zod sigue.
ChatRequestSchema   = { text: string, mode: ModeSchema, session_id?: string }
ChatResponseSchema  = { text: string, actions: ActionSchema[], session_id: string }

// role/content/tool — mirror de ChatMessage
ChatMessageSchema   = { role: "system"|"user"|"assistant"|"tool",
                        content?: string, tool_call_id?: string, name?: string }

// Action = tool ejecutada por el agente Qwen. CON result (decisión cerrada).
// result = { status, ... } cuando salió OK, o { error: { code, message } } si falló.
ActionSchema        = { id: string, name: string,
                        arguments: Record<string, unknown>,
                        result: Record<string, unknown> }

// eventos del stream SSE (con nombre; ver §2.4)
StreamTokenSchema   = { delta: string }
StreamDoneSchema    = { session_id: string, actions: ActionSchema[], finish_reason: string }
StreamErrorSchema   = { code: string, message: string }
```

> **`actions[]`**: **siempre presente** (`actions: Action[]`, vacío si no hubo). En Zod, `z.array(ActionSchema).default([])` — no opcional — para matchear el default de Pydantic. (BriarDevv ya corrigió el `actions?` engañoso en `ENDPOINTS.md`.)
>
> Cada `Action` lleva **`result`** (el resultado ejecutado de la tool, no solo lo pedido): así la UI renderiza *lo que pasó* (chip "evento agendado", card de recordatorio). `result` es el dict que devuelve `ToolRegistry.execute` (hoy stub `{ status: "not_wired" }`; el real cuando se cableen las tools) o `{ error: { code, message } }`. Solo los modos Qwen (productividad, memoria) producen `actions`; Gemma → `[]`.

### 2.3 Sesión (mirror de `apps/backend/app/schemas/session.py`)

```ts
// mirror COMPLETO de SessionOut — no omitir created_at/updated_at.
SessionSchema = { id: string /* UUID */, user_id: string /* UUID */, mode: ModeSchema,
                  started_at: string /* ISO */, ended_at?: string | null,
                  created_at: string /* ISO */, updated_at: string /* ISO */ }
```

> Una **sesión tiene un solo modo** (`SessionOut.mode`). Consecuencia de producto: **cambiar de modo = nueva sesión**, no re-etiquetar la actual.

### 2.4 Streaming — transporte (cerrado)

**Decisión cerrada** (BriarDevv, [`RESPUESTAS-CONTRATO-CHAT.md`](./RESPUESTAS-CONTRATO-CHAT.md)): el streaming va en un **endpoint aparte** `POST /v1/chat/stream`, NO por content-negotiation sobre `/v1/chat`. Razón: semánticas distintas (el no-streaming devuelve un `ChatResponse` con `actions` ya ejecutadas; el stream tiene otro contrato y **sin fallback mid-stream**), y una URL explícita es más clara para el cliente y más fácil de testear.

El stream emite **eventos SSE con nombre** (el `event:` de SSE como discriminador):

```text
event: token
data: {"delta": "Hola"}

event: token
data: {"delta": " mundo"}

event: done
data: {"session_id": "0193...", "actions": [ ... ], "finish_reason": "stop"}
```

- **`token`** → `{ delta }`: un fragmento de texto. El front concatena.
- **`done`** → `{ session_id, actions, finish_reason }`: **evento terminal**, el análogo del `ChatResponse` no-streaming (el `text` el front ya lo acumuló de los `token`).
- **`error`** → `{ code, message }`: solo si algo revienta mid-stream, sin datos de usuario (regla #4). La infra caída NO es `error`: se sirve como respuesta **degradada** (texto degradado vía `token` + `done`).

> El frontend consume estos eventos, **no** el `CompletionChunk` crudo ni el wire OpenAI. (`CompletionChunk` y los fixtures `stream_tool_call_deltas.json` son shape *interno* del cliente vLLM del backend; el endpoint los re-emite como los eventos `token`/`done` de arriba.)

### 2.5 Errores (mirror de `apps/backend/app/llm/errors.py`)

La taxonomía completa del backend (`apps/backend/app/llm/errors.py`, todas heredan de `LlmError`):

| Error | User-facing? | Copy sugerido |
|---|---|---|
| `LlmTimeoutError` | sí | "Me colgué un segundo, ¿lo reintentás?" |
| `LlmUnavailableError` | sí | "No te puedo responder ahora mismo. Probá en un rato." |
| `LlmOverloadedError` | sí | "Estoy saturado, dame un momento y reintentá." |
| `LlmBadRequestError` | sí (raro) | "No pude procesar eso. ¿Lo reformulás?" |
| `LlmContextOverflowError` | sí | "Esta charla se hizo muy larga. Arrancá una nueva." |
| `ModelNotServedError` | interno | genérico "Algo falló" (es config del server) |
| `ToolParsingError` | interno | genérico (no exponer detalle de tools) |
| `ToolExecutionError` | sí (suave) | "No pude completar esa acción." |
| `MemoryRetrievalError` | interno | genérico (degradar sin alarmar) |

El mock devuelve `ApiErrorBody` (`{ error, detail, field? }`, ya existe) con un `error` que mapee a esta taxonomía. La UI mapea cada tipo a su copy humano (los marcados "interno" caen al genérico). El toggle de dev del mock debe poder simular al menos `timeout`, `unavailable` y `overloaded`.

---

## 3. Chat — spec funcional

### 3.1 Flujo

```
home  ──(escribir / elegir recomendación)──▶  crea sesión en el modo activo
                                                      │
                                            /chat/[sessionId]
                                                      │
   ┌──────────────────────────────────────────────────────────────┐
   │  Header: ModeChip(modo) · ModeSwitcher(cambiar = nueva sesión)│
   ├──────────────────────────────────────────────────────────────┤
   │  MessageList                                                  │
   │   · burbuja usuario (derecha)                                 │
   │   · burbuja assistant (izquierda, acento del modo)            │
   │     · streaming token-a-token con cursor                      │
   │     · ActionCard(s) si el modo es Qwen (tool-calls)           │
   ├──────────────────────────────────────────────────────────────┤
   │  ChatComposer (input vivo): textarea + enviar                 │
   │   · Enter envía · Shift+Enter newline · disabled mientras     │
   │     streamea · autosize                                        │
   └──────────────────────────────────────────────────────────────┘
```

### 3.2 Composer (input vivo)

- `ChatComposer` es un **componente nuevo** en `features/chat/` con un `<textarea>` real (no contenteditable). **No** modifica el `ChatInputDocked` de la home: ese sigue deshabilitado hasta la Sesión 5 (ver §4).
- **Enter** envía; **Shift+Enter** newline; autosize hasta N líneas.
- Mientras la respuesta streamea: input **disabled** + botón pasa a "Detener" (cancela el stream).
- Vacío → botón enviar disabled. No mandar mensajes vacíos.
- **Longitud máxima** del mensaje: **~4.000 chars** (decisión cerrada, fundada en el `max_model_len = 4096` de Gemma — el modelo más chico). El backend la enforça (`max_length=4000` → 422); el frontend la valida antes de enviar, con contador al acercarse al límite.
- **Foco**: al enviar, el composer se limpia y el **foco vuelve al textarea** (para encadenar mensajes con teclado).
- Prefill: cuando se llega desde una recomendación de la home, el composer arranca con el `prefillPrompt`.

### 3.3 Mensajes

- **Usuario**: burbuja a la derecha, fondo ink suave. **Optimistic UI**: el mensaje del usuario aparece al instante (al enviar), antes de la respuesta del backend; si la request falla, se marca el mensaje como no-enviado con opción de reintentar.
- **Assistant**: burbuja a la izquierda, con un acento del **tint del modo** (hairline o barra). Mientras streamea, cursor parpadeante; al cerrar (`finish_reason`), se fija.
- **Auto-scroll**: la lista se scrollea sola al fondo mientras llega texto. Si el usuario scrollea hacia arriba manualmente, el auto-scroll **se pausa** (para leer mensajes previos) y aparece un botón "↓ Ir al final"; vuelve a auto-scrollear cuando el usuario baja al fondo.
- **Markdown** (decisión cerrada: **sí, en el MVP**): las respuestas se renderizan con un subset seguro de markdown (bold, listas, inline code, code blocks, links), **sanitizado** (`react-markdown` + `rehype-sanitize`, sin HTML crudo, links con `rel="noopener"`). Motivo: los modelos ya emiten markdown (sobre todo modo Estudio), así que en texto plano se vería `**negrita**` y bloques de código literales. Va en la Sesión 2 (ver §5). **Requiere instalar deps** (`react-markdown`, `rehype-sanitize` — con OK humano, regla #1).
- **Tool / actions** (solo modos Qwen): tras (o dentro de) la respuesta del assistant, `ActionCard`s:
  - `calendar` / `reminder` → "📅 Agendé …" / "⏰ Te recuerdo …" con los `arguments`.
  - `memory` → confirmación de recall/escritura con el **diamante violeta** (símbolo de memoria del onboarding).
- **Estado vacío** de la conversación: saludo breve + intro del modo ("Estás en modo Estudio. Tirame un tema y lo desarmamos.").

### 3.4 Modo y sesión

- El modo se fija **al crear la sesión** (desde la home o el switcher).
- El `ModeSwitcher` en el header: cambiar de modo **arranca una sesión nueva** (no muta la actual). Confirmar con el usuario antes de descartar una conversación a medio escribir.
- El header muestra el `ModeChip` del modo de la sesión.

### 3.5 Errores y resiliencia

- **Timeout / unavailable**: burbuja de sistema con copy humano ("Me colgué un segundo, ¿lo reintentás?") + botón reintentar. Nunca toast genérico.
- **Cancelación**: si el user detiene el stream, se conserva lo recibido hasta ahí, marcado como incompleto.
- **Reduced-motion**: el cursor de streaming y las animaciones de entrada respetan `prefers-reduced-motion` + el override del a11y store.

### 3.6 Sesiones / historial (slice liviano)

- La `EmptySessions` de la home se convierte en una **lista real de sesiones** (mock, persistida local).
- Cada item: modo (ModeChip) + preview del último mensaje + timestamp relativo.
- Click → `/chat/[sessionId]` retoma la conversación.

---

## 4. Arquitectura técnica

### 4.1 Estructura de carpetas (nueva)

```
packages/shared-schemas/src/
└── chat.ts                         ← NUEVO (mirror de app/llm/schemas.py)

apps/web/src/
├── app/
│   ├── chat/
│   │   └── [sessionId]/page.tsx    ← NUEVO (pantalla de conversación)
│   └── home/page.tsx               ← MODIFICAR (arrancar sesión al enviar)
├── features/
│   └── chat/
│       ├── components/
│       │   ├── ChatScreen.tsx
│       │   ├── ChatHeader.tsx
│       │   ├── MessageList.tsx
│       │   ├── MessageBubble.tsx
│       │   ├── ActionCard.tsx
│       │   ├── ChatComposer.tsx     ← NUEVO (textarea vivo; NO toca ChatInputDocked)
│       │   └── EmptyConversation.tsx
│       ├── hooks/
│       │   ├── useChatSession.ts    ← carga/crea sesión
│       │   └── useChatStream.ts     ← lee /v1/chat/stream: SSE events token/done/error
│       ├── store.ts                 ← sesiones + mensajes + status (Zustand)
│       ├── schemas.ts               ← re-export de @ynara/shared-schemas + form-only
│       └── tests/
├── lib/
│   └── chat.ts                      ← cliente: post no-streaming + stream SSE
└── features/home/components/
    ├── ChatInputDocked.tsx          ← MODIFICAR (delega en ChatComposer o navega)
    └── EmptySessions.tsx            ← MODIFICAR (lista real de sesiones)

apps/web/src/lib/api.mocks.ts        ← MODIFICAR (handlers: POST /v1/chat JSON + POST /v1/chat/stream SSE)

tests/e2e/
└── chat.spec.ts                     ← NUEVO
```

### 4.2 Estado y data

- **`features/chat/store.ts`** (Zustand): mapa de sesiones, mensajes por sesión, estado de streaming (`idle | streaming | error`), buffer del chunk en curso. Persistencia local (mock) en `localStorage` con guard SSR (mismo patrón que los stores del onboarding — **storage no-op en server**, ver landmine de zustand 5.0.13). El backend real persiste; el mock guarda local.
- **No-streaming**: TanStack Query mutation que usa `api.post()` de `lib/api.ts` (que ya setea `Accept: application/json`).
- **Streaming**: `useChatStream` pega a `POST /v1/chat/stream` con `fetch` **crudo** + `ReadableStream` + parser de eventos SSE con nombre (`token`/`done`/`error`), **bypasseando `lib/api.ts`** a propósito. Razón: `api.ts` (líneas 40-51) fuerza `Accept: application/json` y consume el body entero con `.json()/.text()` — no sabe de streams. Las dos rutas (no-streaming vía `api.ts` a `/v1/chat`, streaming vía fetch crudo a `/v1/chat/stream`) **no comparten función**. Cancelable vía `AbortController`.
- **IDs de sesión**: `crypto.randomUUID()` en el cliente para el mock (SSR-safe: generar en handler de envío, no en render).

### 4.3 MSW — handlers `/v1/chat` y `/v1/chat/stream`

- **`POST /v1/chat`** (JSON): valida con `ChatRequestSchema` y arma una respuesta canned **según el modo** (tono del modo, ver `docs/product/MODES.md`), con `actions[]` (shape `Action`, con `result`) no vacío solo en modos Qwen.
- **`POST /v1/chat/stream`** (SSE): emite eventos con nombre — varios `event: token` `{ delta }` troceando el texto con delays simulados, y un `event: done` `{ session_id, actions, finish_reason }` al cerrar. En modos Qwen, el `done` lleva `actions` con `result`.
- Toggle de dev para simular errores: `429` (rate limit), `timeout`, `unavailable`, `overloaded`, y un `event: error` mid-stream.
- Copy canned por modo en un `features/chat/constants.ts`, no inline.

### 4.4 Reglas que respeta (de `apps/web/AGENTS.md`)

- **Sin cliente Supabase / sin IA externa** — todo va por `/v1/chat` y `/v1/chat/stream` (FastAPI). El streaming SSE es contra nuestro backend, nunca contra OpenAI/vLLM directo.
- **TS strict, sin `any`** — los `Record<string, unknown>` de `arguments`/`result` se tipan, no `any`. El markdown se renderiza **sanitizado** (`rehype-sanitize`), nunca `dangerouslySetInnerHTML`.
- **Tokens vía CSS variables** — burbujas y acentos usan los tints de modo existentes, nada hardcodeado.
- **TanStack Query** para no-streaming; el streaming es la excepción justificada (un stream no es una query).
- **`prefers-reduced-motion`** respetado en cursor + animaciones.

---

## 5. Plan de ejecución

6 sesiones, 1 PR por sesión.

### 5.1 Sesión 1 — Contrato + infra de chat (mock)
**Branch**: `feat/chat-foundations` · **PR**: `feat(chat): contrato + MSW + store`
1. `packages/shared-schemas/src/chat.ts`: Zod mirror de `ChatRequest`, `ChatResponse`, `ChatMessage`, `Action` (con `result`), `Session`, y los eventos del stream (`StreamToken`/`StreamDone`/`StreamError`). Export en el barrel.
2. `features/chat/store.ts` (sesiones + mensajes + status, persist local con storage no-op en SSR).
3. `lib/chat.ts`: cliente no-streaming (`POST /v1/chat`, vía `api.post`).
4. `api.mocks.ts`: handler `/v1/chat` no-streaming, respuesta canned por modo (con `actions` solo en Qwen).
5. Smoke en `/test-mock` (o equivalente).

**Done**: `/v1/chat` mock devuelve un `ChatResponse` válido por modo; el store guarda la conversación.

### 5.2 Sesión 2 — Pantalla de conversación (no-streaming)
**Branch**: `feat/chat-screen` · **PR**: `feat(chat): pantalla de conversación`
1. Ruta `app/chat/[sessionId]/page.tsx` + dispatcher de sesión, **con guards**:
   - si `!onboardingCompleted` → redirect a `/onboarding`.
   - si el `sessionId` de la URL no existe en el store → redirect a `/home` con toast "Conversación no encontrada".
2. `ChatScreen`, `ChatHeader` (ModeChip), `MessageList`, `MessageBubble`, `EmptyConversation`.
3. `ChatComposer` (textarea vivo: Enter envía, Shift+Enter newline, autosize, disabled-states, foco vuelve al enviar, límite de ~4000 chars).
4. Enviar → **optimistic** (el mensaje del user aparece al instante) → `POST /v1/chat` → render de la respuesta (sin streaming todavía); si falla, marcar el mensaje como no-enviado + reintentar.
5. **Markdown sanitizado** en `MessageBubble` (instalar `react-markdown` + `rehype-sanitize` **con OK humano**; subset seguro, sin HTML crudo, links `rel="noopener"`).
6. Copy canned y de estados vacíos en un `features/chat/constants.ts` (no inline), con el tono de cada modo según `docs/product/MODES.md` — facilita i18n futuro.

**Done**: se manda un mensaje y se ve la respuesta del modo; estado vacío correcto; URL inválida y user no-onboardeado redirigen bien.

### 5.3 Sesión 3 — Streaming (SSE)
**Branch**: `feat/chat-streaming` · **PR**: `feat(chat): streaming de respuestas`
1. `api.mocks.ts`: handler `POST /v1/chat/stream` (SSE) que emite `event: token` `{ delta }` con delays + `event: done` `{ session_id, actions, finish_reason }` al cerrar.
2. `useChatStream` (fetch crudo a `/v1/chat/stream` + ReadableStream + parser de eventos SSE con nombre `token`/`done`/`error` + `AbortController`).
3. Render token-a-token con cursor; "Detener" cancela y conserva lo recibido (marcado incompleto).
4. **Auto-scroll** al fondo mientras llega texto; se pausa si el user scrollea arriba (+ botón "↓ Ir al final").
5. `aria-live="polite"` en la burbuja que streamea; reduced-motion respetado.

**Done**: la respuesta aparece token a token; se puede cancelar; auto-scroll correcto; SR la anuncia sin spamear.

### 5.4 Sesión 4 — Tool-calls / actions (modos Qwen)
**Branch**: `feat/chat-actions` · **PR**: `feat(chat): acciones de tools en modos Qwen`
1. `ActionCard` (calendar/reminder/memory; memory con diamante violeta), renderiza `name` + `arguments` + **`result`** (estado ejecutado o error).
2. Mock: en modos Qwen (productividad, memoria) emitir `actions[]` con shape `Action` (con `result`); en Gemma, vacío.
3. Render de `actions[]` desde el `ChatResponse` (no-streaming) y desde el `event: done` (streaming).

**Done**: productividad/memoria muestran acciones; estudio/bienestar/vida no.

### 5.5 Sesión 5 — Integración home + modos + sesiones
**Branch**: `feat/chat-home` · **PR**: `feat(chat): arranque desde home + historial de sesiones`
1. Home: enviar desde `ChatInputDocked` o elegir recomendación → crea sesión en el modo correcto → navega a `/chat/[id]` con prefill.
2. `ModeSwitcher`: cambiar de modo arranca sesión nueva (con confirmación si hay borrador).
3. `EmptySessions` → `SessionsList` real (mock): retomar conversaciones.

**Done**: flujo home → chat completo; historial navegable.

### 5.6 Sesión 6 — Tests + a11y + pulido
**Branch**: `feat/chat-tests` · **PR**: `test(chat): vitest + playwright + axe`
1. vitest: store, parser SSE, render de mensajes/acciones, lógica Qwen-vs-Gemma.
2. e2e: mandar mensaje → streamed response → ver conversación; modo Qwen con acción; path de error; axe en `/chat/[id]`.
3. a11y: live region, foco, teclado; responsive 375/768/1280.
4. `pnpm --filter @ynara/web typecheck && lint && test` verde; `bash scripts/ynara-doctor.sh` exit 0.

**Done**: red de tests verde; doctor exit 0.

### 5.7 Estrategia de PRs

| # | PR | Branch | Tamaño | Reviewer |
|---|---|---|---|---|
| 1 | `feat(chat): contrato + MSW + store` | `feat/chat-foundations` | M | @BriarDevv (contrato) |
| 2 | `feat(chat): pantalla de conversación` | `feat/chat-screen` | L | @querques20 (UX) |
| 3 | `feat(chat): streaming de respuestas` | `feat/chat-streaming` | M | @BriarDevv |
| 4 | `feat(chat): acciones de tools (Qwen)` | `feat/chat-actions` | M | @querques20 |
| 5 | `feat(chat): arranque desde home + sesiones` | `feat/chat-home` | M | @querques20 |
| 6 | `test(chat): vitest + playwright + axe` | `feat/chat-tests` | M | @BriarDevv |

> **Antes de cada PR**: rebasar sobre `origin/main` fresco (el doctor lo exige). El repo se mueve rápido — no construir sobre un `main` local desactualizado.

**Corte natural**: tras Sesión 4 el chat ya es usable de punta a punta con streaming + acciones; Sesión 5 (home + historial) y 6 (tests) se pueden diferir si aprieta.

---

## 6. Definition of Done

### Repo / proceso
- [ ] 6 PRs mergeados a `main` (rebasados sobre `origin/main` fresco; doctor exit 0 en cada uno).
- [ ] Sin `any`, sin `@ts-ignore` sin justificación. Sin `@supabase/supabase-js`, sin `openai/anthropic/google-genai`.
- [ ] Zod del chat = mirror de `app/llm/schemas.py` (sin divergencia silenciosa).

### Chat funcional
- [ ] Mandar un mensaje (`POST /v1/chat`) y recibir respuesta del modo activo.
- [ ] Streaming (`POST /v1/chat/stream`, eventos `token`/`done`/`error`) token-a-token con cursor; cancelable.
- [ ] Respuestas con **markdown sanitizado** (bold, listas, code, links), sin HTML crudo.
- [ ] Modos Qwen (productividad, memoria) muestran `actions[]` con `result`; modos Gemma no.
- [ ] Estados de error humanos por tipo (timeout/unavailable/overloaded/429), con reintento.
- [ ] Cambiar de modo arranca sesión nueva.

### Sesiones
- [ ] La home arranca una sesión al enviar / elegir recomendación, en el modo correcto.
- [ ] Historial de sesiones navegable; retomar una conversación.

### A11y
- [ ] `aria-live` en la respuesta que streamea; SR la anuncia sin spamear.
- [ ] Tab/Enter/Shift+Enter coherentes en el composer; foco gestionado.
- [ ] `prefers-reduced-motion` respetado (cursor + animaciones) + override del a11y store.
- [ ] axe sin violations críticas en `/chat/[id]`.

### Responsive
- [ ] 375 / 768 / 1280 verificado (screenshots en el PR).

---

## 7. Riesgos y landmines

> El contrato del chat quedó **cerrado** por @BriarDevv en [`RESPUESTAS-CONTRATO-CHAT.md`](./RESPUESTAS-CONTRATO-CHAT.md) (PR #61): streaming en `/v1/chat/stream` con eventos `token`/`done`/`error`, `Action` con `result`, `actions` siempre presente, markdown sí, límite ~4000 chars. Las preguntas de la antigua §7.1 ya no están abiertas (ver §7.1 abajo).

**Auth es prerequisito del backend real, no del mock.** El `/v1/chat` real pide usuario autenticado, pero `core/security.py` está en `NotImplementedError`. El mock no exige auth. Cuando se conecte al backend real, hace falta: (a) el PR de auth del backend, (b) la inyección de `Authorization: Bearer <token>` en `lib/api.ts` (hoy un TODO). Sin eso, el chat real devuelve 401.

**Pydantic gana, Zod sigue.** Los Zod del chat son mirror de `app/llm/schemas.py`. Si el backend toca esos schemas, corregir el mirror en el mismo PR. La ventaja sobre auth: acá el Pydantic **ya existe**, así que la divergencia es detectable desde el día 1.

**Una sesión = un modo.** No re-etiquetar la conversación al cambiar de modo: arrancar sesión nueva (coherente con `SessionOut.mode`).

**Streaming no es una query.** Usar TanStack Query para el caso no-streaming, pero el stream va con `fetch` + `ReadableStream` + `AbortController` en `useChatStream`. No forzar el stream dentro de Query.

**`crypto.randomUUID` para IDs de sesión en el mock** — generar en el handler de envío (cliente), SSR-safe; nunca en render.

**Storage de zustand SSR-safe** — el store del chat persiste local; usar el patrón de storage **no-op en server** (`StateStorage`), no `undefined` (la factory de zustand 5.0.13 no lo acepta — landmine ya conocida del onboarding).

**El frontend no toca memoria.** La memoria (semantic/episodic/procedural) la maneja el backend async vía Celery, fuera del path de respuesta. El frontend solo **muestra** confirmaciones de memoria que vengan en `actions[]`; no escribe ni lee memoria directo.

**No persistir "de verdad".** El mock guarda sesiones/mensajes en `localStorage`; cuando exista el backend, la persistencia es de él. No construir lógica que asuma persistencia local permanente. Cuando el backend reemplace el mock, las sesiones locales se pierden (no hay migración) — aceptable para MVP, anotarlo en el PR.

**Rate limiting.** `ENDPOINTS.md` prevé ~30/min por usuario (TODO del backend). El mock debe poder simular un `429` para probar la UX de cooldown (ej. deshabilitar el envío con copy "Esperá unos segundos"). No construir un rate-limiter real en el cliente.

### 7.1 Decisiones cerradas (eran preguntas abiertas)

Cerradas por @BriarDevv en [`RESPUESTAS-CONTRATO-CHAT.md`](./RESPUESTAS-CONTRATO-CHAT.md) (PR #61) + decisión del owner:

| # | Pregunta | Decisión |
|---|---|---|
| 1 | ¿Streaming por content-negotiation o endpoint aparte? | **Endpoint aparte `POST /v1/chat/stream`** (SSE). `/v1/chat` queda no-streaming. |
| 2 | ¿Shape del evento terminal? | **Eventos SSE con nombre**: `token {delta}`, `done {session_id, actions, finish_reason}`, `error {code, message}`. |
| 3 | ¿`actions[]` con `result`? | **Sí**: `Action = { id, name, arguments, result }`. |
| 4 | ¿`actions?` o `actions: Action[]`? | **`actions: Action[]`** (siempre presente). Ya corregido en `ENDPOINTS.md`. |
| 5 | ¿Markdown en las respuestas? | **Sí**, subset seguro sanitizado desde el MVP (owner). |
| 6 | ¿Máximo de longitud del mensaje? | **~4.000 chars** (techo seguro contra el `max_model_len` de Gemma). |

---

## 8. Referencias cruzadas

- [`AGENTS.md`](../../AGENTS.md) — 10 reglas no negociables (#4 sin IA externa, #5 sin Supabase en frontend).
- [`apps/web/AGENTS.md`](../../apps/web/AGENTS.md) — reglas duras del frontend web.
- [`apps/backend/app/llm/schemas.py`](../../apps/backend/app/llm/schemas.py) — **contrato fuente** (ChatRequest/Response, ChatMessage, ToolCall, CompletionChunk).
- [`docs/planning/RESPUESTAS-CONTRATO-CHAT.md`](./RESPUESTAS-CONTRATO-CHAT.md) — **respuestas de contrato cerradas** (@BriarDevv, PR #61): streaming, eventos, `Action.result`, markdown, límite.
- [`apps/backend/docs/ENDPOINTS.md`](../../apps/backend/docs/ENDPOINTS.md) — spec de `POST /v1/chat` + `POST /v1/chat/stream` (M9).
- [`docs/planning/LLM-INFERENCE-INTEGRATION.md`](./LLM-INFERENCE-INTEGRATION.md) — milestones del backend LLM (M8 router, M9 endpoint).
- [`docs/product/MODES.md`](../product/MODES.md) — definición + tono de los 5 modos.
- [`docs/architecture/adrs/ADR-002-gemma-qwen-dual-stack.md`](../architecture/adrs/ADR-002-gemma-qwen-dual-stack.md) — Gemma lee / Qwen escribe + tools.
- [`ynara.config.json`](../../ynara.config.json) — config canónica de modos.
- [`docs/planning/archive/FRONTEND-ONBOARDING-PLAN.md`](./archive/FRONTEND-ONBOARDING-PLAN.md) — el slice anterior (ejecutado), mismo formato.

---

> **Cómo usar este documento**: cada sesión arranca con un PR scope claro y termina con un Done explícito. Si cambia el scope o el contrato del backend, editar este doc en el mismo PR. Cuando todas las sesiones cierren, marcar como "ejecutado" y mover a `docs/planning/archive/`.
