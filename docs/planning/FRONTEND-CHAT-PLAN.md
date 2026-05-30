# Frontend · Chat / Conversación (modo) — Plan completo (web + mobile)

> **Estado**: v2 — borrador para revisión
> **Fecha**: 2026-05-30 (v1 web-only) · 2026-05-30 (v2 web + mobile)
> **Owner**: @MateoGs013
> **Reviewers sugeridos**: @BriarDevv (contrato LLM / backend), @querques20 (UX / UI)
> **Alcance**: `apps/web` (Next.js) **+** `apps/mobile` (Expo). Mock-first con MSW en ambas. Capa compartida en `packages/shared-schemas` y `packages/shared-types`.
> **Continúa**: [`archive/FRONTEND-ONBOARDING-PLAN.md`](./archive/FRONTEND-ONBOARDING-PLAN.md) (ejecutado, web).

> **Qué cambió de v1 → v2**: v1 era web-only. v2 suma el track **mobile (Expo)**, factoriza el contrato y la lógica SSE en una **capa compartida** (§3), separa la spec en diseño técnico compartido + spec funcional común + arquitecturas por plataforma, y agrega fases y landmines propias de mobile (streaming con `expo/fetch`, NativeWind 4-sobre-TW3, design system mobile inexistente, SecureStore). El contrato del chat (§2) **no cambió**: sigue siendo el cerrado en #61.

---

## 0. Contexto

Este documento es el plan del **segundo slice navegable** del frontend de Ynara: la **pantalla de conversación** (chat con el asistente, consciente del modo activo), en **web y mobile**. El onboarding web ya está mergeado y la home web vacía ya **promete** el chat (el `ChatInputDocked` está deshabilitado con tooltip "Próximamente"). Este plan lo hace real, y arranca el camino equivalente en mobile.

**Enfoque: mock-first con MSW** en las dos plataformas. El backend tiene la capa LLM como librería (clientes vLLM, streaming, tool-calls, routing por modo) pero **todavía no expone `POST /v1/chat` por HTTP** (es el milestone M9, pendiente) y **el auth recién aterrizó** (`core/security.py` se implementó en #62, pero el endpoint de chat real todavía no existe ni está cableado a auth). Por eso construimos contra mocks y nos conectamos al backend real cuando M9 cierre.

**La ventaja clave frente al onboarding**: el contrato del chat **ya existe en Pydantic** (`apps/backend/app/llm/schemas.py`: `ChatRequest` / `ChatResponse` / `ChatMessage` / `ToolCall` / `CompletionChunk`) y el endpoint está spec'eado en [`apps/backend/docs/ENDPOINTS.md`](../../apps/backend/docs/ENDPOINTS.md). O sea, a diferencia del contrato de auth (que recién se está cerrando), **el mock del chat puede espejar un Pydantic real** → la regla "Pydantic gana, Zod sigue" aplica desde el día 1 y la divergencia es detectable en code review. Y porque el contrato es **agnóstico de plataforma**, web y mobile comparten los mismos schemas y la misma máquina de estados.

### Por qué este plan existe ahora

- El onboarding dejó al usuario web en una home que no hace nada todavía: el siguiente paso obvio es **hablar con Ynara**.
- El backend ya definió el contrato del router (`route(ChatRequest) -> ChatResponse`) y el formato de streaming. Construir el frontend contra ese contrato ahora minimiza retrabajo cuando M9 cierre.
- Es el core del producto: sin chat, Ynara es un onboarding lindo sin sustancia.
- **Sumar mobile ahora** evita que las dos plataformas diverjan en cómo modelan la conversación: si la lógica de sesiones/mensajes/streaming se factoriza compartida desde el día 1, mobile no reinventa el contrato ni la máquina de estados.

### Realidad de cada plataforma (de dónde parte cada track)

| | **web** (`apps/web`) | **mobile** (`apps/mobile`) |
|---|---|---|
| Onboarding | ✅ mergeado | ❌ no existe |
| Home | ✅ vacía con recomendaciones | ❌ no existe |
| Design system / tokens | ✅ `globals.css`, tints por modo, primitives | ❌ scaffold pelado, sin tokens propios |
| Cliente HTTP | ✅ `lib/api.ts` tipado | ❌ no existe |
| Stores (Zustand) | ✅ `user`, `a11y` | ❌ no existe |
| MSW | ✅ handlers + toggle | ❌ no configurado (`msw/native`) |
| Navegación | ✅ App Router | ✅ Expo Router (solo `_layout` + `index` placeholder) |

> **Consecuencia de planificación**: el track **web** del chat es incremental (reúsa todo lo del onboarding). El track **mobile** arrastra un prerequisito grande — **fundaciones mobile** (DS con NativeWind, providers, cliente HTTP, MSW native, auth con SecureStore) — que hoy no existen. Este plan **no** reconstruye todo el onboarding mobile: scopea las fundaciones **mínimas** que el chat necesita y deja el resto como dependencia explícita. Ver §6 y §7.

---

## Tabla de contenidos

1. [Qué heredamos](#1-qué-heredamos)
2. [El contrato del chat (mirror del backend)](#2-el-contrato-del-chat-mirror-del-backend)
3. [Diseño técnico compartido (web + mobile)](#3-diseño-técnico-compartido-web--mobile)
4. [Chat — spec funcional](#4-chat--spec-funcional)
5. [Arquitectura web](#5-arquitectura-web)
6. [Arquitectura mobile](#6-arquitectura-mobile)
7. [Plan de ejecución](#7-plan-de-ejecución)
8. [Definition of Done](#8-definition-of-done)
9. [Riesgos y landmines](#9-riesgos-y-landmines)
10. [Referencias cruzadas](#10-referencias-cruzadas)

---

## 1. Qué heredamos

### 1.1 Web (del slice de onboarding ya mergeado)

| Pieza | Dónde | Uso en el chat |
|---|---|---|
| Design system + tokens | `apps/web/src/app/globals.css` | Burbujas, tints por modo, motion |
| Tints por modo | `apps/web/src/components/ui/modes.ts` (`MODES`, `gradientClass`) | Acento de cada conversación según modo |
| `ModeChip` | `apps/web/src/components/ui/ModeChip.tsx` | Header de la conversación + switcher |
| `ModeSwitcher` | `apps/web/src/features/home/components/ModeSwitcher.tsx` | Cambiar de modo (= nueva sesión) |
| `ChatInputDocked` | `apps/web/src/features/home/components/ChatInputDocked.tsx` | **Se evoluciona** a composer real |
| Fetcher tipado + `ApiError` | `apps/web/src/lib/api.ts` | Requests al `/v1/chat` mock |
| Infra MSW + toggle | `apps/web/src/lib/api.mocks.ts`, `lib/env.ts` (`shouldEnableMocks`) | Handlers del chat |
| `useUserStore` | `apps/web/src/stores/user.ts` | `displayName`, `interestedModes`, `token` |
| Stack de tests | vitest + RTL + playwright + axe | Misma red para el chat |

### 1.2 Mobile (lo que ya está)

| Pieza | Dónde | Estado |
|---|---|---|
| Expo Router | `apps/mobile/src/app/_layout.tsx`, `index.tsx` | Solo `Stack` + placeholder; **TODO** providers |
| Stack de libs | `apps/mobile/package.json` | Expo 53, Expo Router, RN 0.76, React 19, NativeWind 4 (sobre TW3), TanStack Query, Zustand, Zod, `expo-secure-store`, `expo-notifications` |
| Reglas | `apps/mobile/AGENTS.md` | Sin Supabase, sin IA externa, TS strict, tokens compartidos con web, **SecureStore obligatorio** para JWT |

> Mobile **no hereda casi nada construido** — hereda el **stack elegido** y las reglas. Las fundaciones reales (DS, api client, stores, MSW) son parte del prerequisito del track mobile (§6, §7).

### 1.3 Compartido (packages)

| Pieza | Dónde | Uso |
|---|---|---|
| `@ynara/shared-schemas` (Zod) | `packages/shared-schemas/` | **Donde viven los Zod del chat** (§3) |
| `@ynara/shared-types` (TS) | `packages/shared-types/` | Tipos TS sin runtime (mirror manual de Pydantic) |
| `ModeSchema` / `MemoryLayerSchema` | `packages/shared-schemas/src/modes.ts` | Enum de modos, consumido por web + mobile |

**Modos** (de [`ynara.config.json`](../../ynara.config.json), no hardcodear):

| Modo | Modelo | Rol | Tools | Memoria |
|---|---|---|---|---|
| productividad | qwen-3.5-9b | **agente** | calendar, reminder, memory | semantic + episodic |
| estudio | gemma-4-26b-a4b | conversacional | — | episodic + procedural |
| bienestar | gemma-4-26b-a4b | conversacional | — | procedural + semantic |
| vida | gemma-4-26b-a4b | conversacional | — | procedural |
| memoria | qwen-3.5-9b | **agente** | memory | las 3 capas |

> **Regla de oro del routing** (ADR-002): **Qwen** (productividad, memoria) ejecuta tools y escribe memoria → produce `actions[]`. **Gemma** (estudio, bienestar, vida) solo conversa y lee memoria → `actions[]` vacío. La UI (web y mobile) tiene que reflejar esta diferencia.

> **Nota de fuente**: la tabla de routing de `AGENTS.md` lista `vida` con "calendar (read)", pero `ynara.config.json` (`tools_enabled: []`), `MODES.md` y ADR-002 coinciden en que **Gemma no llama tools**. Acá manda la config canónica: `vida` sin tools. Vale corregir el resumen de `AGENTS.md` en un PR aparte (queda como deuda, no parte de este plan).

---

## 2. El contrato del chat (mirror del backend)

> **Platform-agnostic.** Esta sección es idéntica para web y mobile: el contrato es del backend, las dos plataformas lo espejan vía la capa compartida (§3).

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

  Auth:     usuario autenticado (mock no lo exige)
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

> **Importante para mobile**: el formato del **wire** (eventos SSE con nombre) es el mismo en las dos plataformas. Lo que cambia es **cómo se lee el stream** (browser `ReadableStream` vs `expo/fetch` en RN) — ver §3.4 y §6. El **parser** de eventos SSE es lógica pura, compartida.

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

El mock devuelve `ApiErrorBody` (`{ error, detail, field? }`, ya existe) con un `error` que mapee a esta taxonomía. La UI mapea cada tipo a su copy humano (los marcados "interno" caen al genérico). El copy es **compartido** (vive en `packages/`, ver §3.3) para no divergir entre web y mobile. El toggle de dev del mock debe poder simular al menos `timeout`, `unavailable` y `overloaded`.

---

## 3. Diseño técnico compartido (web + mobile)

> El corazón de v2: **lo que es lógica de dominio (no UI) se factoriza compartido** para que web y mobile no diverjan. La UI (componentes, motion, layout) es por plataforma.

### 3.1 Qué se comparte y qué no

| Capa | Compartida | Por plataforma |
|---|---|---|
| Schemas Zod del contrato (§2.2) | ✅ `packages/shared-schemas/src/chat.ts` | — |
| Tipos TS derivados | ✅ `packages/shared-types` (o `z.infer` desde shared-schemas) | — |
| Parser de eventos SSE (lógica pura) | ✅ ver §3.4 | — |
| Copy por modo + mapeo de errores | ✅ `packages/shared-schemas` o `shared-types` (constantes) | — |
| Máquina de estados de la conversación (qué es un mensaje, status, optimistic, cancelación) | ✅ contrato del store (shape) | Implementación del store (Zustand) puede ser por plataforma o compartida |
| Cliente HTTP (no-streaming) | ⚠️ patrón compartido, impl. por plataforma | `web/lib/api.ts`, `mobile/lib/api.ts` |
| Lectura del stream (transporte) | ❌ | browser `fetch`+`ReadableStream` (web) vs `expo/fetch` (mobile) |
| Componentes UI, motion, layout | ❌ | web (Tailwind v4) / mobile (NativeWind) |

> **Por qué el store no se mueve a `packages/ui` todavía**: `apps/web/AGENTS.md` dice que `packages/ui` está reservado para componentes **realmente** RN-compatibles y "por ahora vacío. No mover primitives acá hasta que haya consumidor mobile". El chat **es** el primer consumidor mobile real, así que este plan **sí** habilita compartir lógica — pero en `packages/shared-*` (data/lógica), no `packages/ui` (componentes), que sigue siendo decisión aparte.

### 3.2 Schemas Zod compartidos — `packages/shared-schemas/src/chat.ts` (NUEVO)

Mirror de `app/llm/schemas.py` (§2.2). Exportar desde el barrel `packages/shared-schemas/src/index.ts`. Reglas:

- `ChatRequestSchema`, `ChatResponseSchema`, `ChatMessageSchema`, `ActionSchema`, `SessionSchema`, y los eventos `StreamTokenSchema` / `StreamDoneSchema` / `StreamErrorSchema`.
- `actions: z.array(ActionSchema).default([])` — nunca opcional.
- `text: z.string().min(1).max(4000)` — espeja el `Field(max_length=4000)` del backend (§9, decisión #6).
- Reusar `ModeSchema` de `modes.ts` (no redefinir el enum).
- También sumar los tipos a `packages/shared-types/src/index.ts` (hoy con TODO `Chat/Session`), o exportarlos vía `z.infer` desde shared-schemas para no duplicar — **decisión a tomar en la fase de fundaciones** (§7.1). Recomendado: `z.infer` desde shared-schemas como única fuente, y que shared-types re-exporte el tipo si hace falta sin Zod.

### 3.3 Copy y constantes compartidas

Para no escribir dos veces el copy de errores ni el tono por modo:

- **Mapeo error → copy humano** (tabla §2.5): una función pura `chatErrorCopy(code: string): string` en `packages/shared-schemas` (o un objeto const). Web y mobile la consumen igual.
- **Copy canned por modo** del mock (saludos, intro de modo, respuestas de ejemplo): vive en `packages/` para que los dos mocks devuelvan lo mismo. El **tono** de cada modo sale de [`docs/product/MODES.md`](../product/MODES.md).
- **Esto facilita i18n** futuro: todo el texto de usuario en un solo lugar.

### 3.4 Parser de eventos SSE — lógica pura compartida (NUEVO)

El **parsing** de un stream SSE con eventos con nombre (`event: token\ndata: {...}\n\n`) es lógica pura, idéntica en las dos plataformas. Lo que difiere es **de dónde salen los bytes** (transporte). Por eso:

- **Compartido**: un parser incremental que toma chunks de texto y emite eventos tipados `{ type: "token" | "done" | "error", data: ... }`, validados con los Zod de §3.2. Idealmente un generador/transformador que no sabe de `fetch`. Ubicación sugerida: `packages/shared-schemas/src/sse.ts` (o un `packages/shared-core` si crece). Testeable con los fixtures `.sse` del backend.
- **Por plataforma (transporte)**: quién le da los chunks al parser.
  - **Web**: `fetch(url)` → `response.body.getReader()` (`ReadableStream`) → decodificar → alimentar el parser. `lib/api.ts` no sirve acá (consume el body entero con `.json()/.text()`), por eso el stream usa `fetch` crudo + `AbortController`.
  - **Mobile**: el `fetch` global de React Native **no expone `response.body` como `ReadableStream`** (devuelve el body entero). La solución en Expo 53 es **`expo/fetch`** (fetch WinterCG con streaming: `import { fetch } from "expo/fetch"` → `response.body.getReader()`). Alternativa de fallback si `expo/fetch` no alcanza: librería `react-native-sse` (EventSource para RN) o XHR con `onprogress`. **Decisión recomendada: `expo/fetch`**, a validar en spike (ver §9, landmine mobile-streaming).

```
            ┌─────────────────────────────┐
            │  parser SSE (compartido)     │   ← lógica pura, testeada con fixtures .sse
            │  chunks de texto → eventos   │
            │  {token|done|error} (Zod)    │
            └──────────────▲──────────────┘
                           │ chunks
        ┌──────────────────┴───────────────────┐
        │                                        │
 web: fetch + ReadableStream          mobile: expo/fetch + ReadableStream
   (lib/chat.ts, AbortController)        (lib/chat.ts, AbortController)
```

### 3.5 Contrato del store de conversación (shape compartido)

Las dos plataformas modelan la conversación igual (aunque cada una tenga su `store.ts` Zustand). Shape mínimo:

- `sessions: Record<sessionId, Session>` (modo, timestamps).
- `messages: Record<sessionId, Message[]>` donde `Message = { id, role, text, status, actions? }` y `status ∈ { sending, streaming, done, error, canceled }`.
- `streamStatus: "idle" | "streaming" | "error"` + buffer del chunk en curso.
- Acciones: `createSession(mode)`, `appendUserMessage(optimistic)`, `startAssistantMessage()`, `appendDelta(delta)`, `finalize(done)`, `failMessage(error)`, `cancel()`.
- **Persistencia local (mock)**: web → `localStorage` (con storage no-op en SSR, landmine zustand 5.0.13); mobile → `AsyncStorage`/`expo-secure-store` **no** para mensajes (no son secretos) — usar `@react-native-async-storage/async-storage` para el historial mock, y SecureStore **solo** para el token (regla mobile #5). El backend real persiste; el mock guarda local en ambas.

---

## 4. Chat — spec funcional

> UX común a web y mobile. Las diferencias de plataforma se marcan **[web]** / **[mobile]**.

### 4.1 Flujo

```
home  ──(escribir / elegir recomendación)──▶  crea sesión en el modo activo
                                                      │
                                            /chat/[sessionId]   (web)
                                            /chat/[sessionId]   (mobile, Expo Router)
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
   │  ChatComposer (input vivo): textarea/TextInput + enviar       │
   │   · Enter envía · Shift+Enter newline · disabled mientras     │
   │     streamea · autosize                                        │
   └──────────────────────────────────────────────────────────────┘
```

### 4.2 Composer (input vivo)

- Componente **nuevo** en `features/chat/`. **[web]** `<textarea>` real (no contenteditable). **[mobile]** `<TextInput multiline>` con `KeyboardAvoidingView` para que el teclado no tape el input.
- **[web]** En la home, **no** modifica el `ChatInputDocked`: ese sigue deshabilitado hasta la fase de integración (§7). **[mobile]** no hay home todavía; el composer vive directo en la pantalla de chat.
- **Enviar**: **[web]** Enter envía, Shift+Enter newline. **[mobile]** botón de enviar explícito (en touch no hay "Shift+Enter"); Enter inserta newline.
- Mientras la respuesta streamea: input **disabled** + botón pasa a "Detener" (cancela el stream).
- Vacío → botón enviar disabled. No mandar mensajes vacíos.
- **Longitud máxima** del mensaje: **~4.000 chars** (decisión cerrada, fundada en el `max_model_len = 4096` de Gemma — el modelo más chico). El backend la enforça (`max_length=4000` → 422); el frontend la valida antes de enviar, con contador al acercarse al límite.
- **Foco**: al enviar, el composer se limpia. **[web]** el foco vuelve al textarea (encadenar con teclado). **[mobile]** mantener el teclado abierto.
- Prefill: cuando se llega desde una recomendación de la home **[web]**, el composer arranca con el `prefillPrompt`.

### 4.3 Mensajes

- **Usuario**: burbuja a la derecha, fondo ink suave. **Optimistic UI**: el mensaje del usuario aparece al instante (al enviar), antes de la respuesta del backend; si la request falla, se marca como no-enviado con opción de reintentar.
- **Assistant**: burbuja a la izquierda, con un acento del **tint del modo** (hairline o barra). Mientras streamea, cursor parpadeante; al cerrar (`finish_reason`), se fija.
- **Auto-scroll**: la lista se scrollea sola al fondo mientras llega texto. Si el usuario scrollea hacia arriba manualmente, el auto-scroll **se pausa** y aparece un botón "↓ Ir al final"; vuelve a auto-scrollear cuando el usuario baja al fondo. **[mobile]** se implementa con `FlatList` (idealmente `inverted` o `maintainVisibleContentPosition`) en vez de `ScrollView` para listas largas.
- **Markdown** (decisión cerrada: **sí, en el MVP**): subset seguro (bold, listas, inline code, code blocks, links), **sanitizado**, sin HTML crudo, links con `rel="noopener"`. Motivo: los modelos ya emiten markdown (sobre todo modo Estudio). **Requiere instalar deps con OK humano (regla #1)**:
  - **[web]** `react-markdown` + `rehype-sanitize`.
  - **[mobile]** `react-native-markdown-display` (u otra lib RN equivalente; **a validar** que soporte el subset y sea segura — no hay `rehype` en RN). El renderizado del subset tiene que verse coherente entre plataformas.
- **Tool / actions** (solo modos Qwen): tras (o dentro de) la respuesta del assistant, `ActionCard`s:
  - `calendar` / `reminder` → "📅 Agendé …" / "⏰ Te recuerdo …" con los `arguments`.
  - `memory` → confirmación de recall/escritura con el **diamante violeta** (símbolo de memoria del onboarding).
- **Estado vacío** de la conversación: saludo breve + intro del modo ("Estás en modo Estudio. Tirame un tema y lo desarmamos.").

### 4.4 Modo y sesión

- El modo se fija **al crear la sesión** (desde la home **[web]** o el switcher).
- El `ModeSwitcher` en el header: cambiar de modo **arranca una sesión nueva** (no muta la actual). Confirmar con el usuario antes de descartar una conversación a medio escribir.
- El header muestra el `ModeChip` del modo de la sesión.

### 4.5 Errores y resiliencia

- **Timeout / unavailable**: burbuja de sistema con copy humano (§2.5) + botón reintentar. Nunca toast genérico.
- **Cancelación**: si el user detiene el stream, se conserva lo recibido hasta ahí, marcado como incompleto.
- **Reduced-motion**: el cursor de streaming y las animaciones de entrada respetan `prefers-reduced-motion`. **[web]** + override del a11y store. **[mobile]** `AccessibilityInfo.isReduceMotionEnabled()`.

### 4.6 Sesiones / historial (slice liviano)

- **[web]** La `EmptySessions` de la home se convierte en una **lista real de sesiones** (mock, persistida local).
- **[mobile]** una pantalla/lista equivalente cuando exista la home mobile (puede diferirse; ver §7).
- Cada item: modo (ModeChip) + preview del último mensaje + timestamp relativo. Click → `/chat/[sessionId]` retoma la conversación.

---

## 5. Arquitectura web

### 5.1 Estructura de carpetas (web)

```
packages/shared-schemas/src/
├── chat.ts                         ← NUEVO (mirror de app/llm/schemas.py)
└── sse.ts                          ← NUEVO (parser SSE puro, compartido)

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
│       │   └── useChatStream.ts     ← lee /v1/chat/stream: SSE token/done/error
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

### 5.2 Estado y data (web)

- **`features/chat/store.ts`** (Zustand): shape de §3.5. Persistencia local en `localStorage` con guard SSR (storage **no-op en server**, landmine zustand 5.0.13).
- **No-streaming**: TanStack Query mutation que usa `api.post()` de `lib/api.ts` (que ya setea `Accept: application/json`).
- **Streaming**: `useChatStream` pega a `POST /v1/chat/stream` con `fetch` **crudo** + `ReadableStream` + el parser SSE compartido (§3.4), **bypasseando `lib/api.ts`** a propósito (consume el body entero con `.json()/.text()`, no sabe de streams). Cancelable vía `AbortController`.
- **IDs de sesión**: `crypto.randomUUID()` en el cliente para el mock (SSR-safe: generar en handler de envío, no en render).

### 5.3 MSW (web) — handlers `/v1/chat` y `/v1/chat/stream`

- **`POST /v1/chat`** (JSON): valida con `ChatRequestSchema` y arma una respuesta canned **según el modo** (copy compartido, §3.3), con `actions[]` (shape `Action`, con `result`) no vacío solo en modos Qwen.
- **`POST /v1/chat/stream`** (SSE): emite eventos con nombre — varios `event: token` `{ delta }` troceando el texto con delays simulados, y un `event: done` `{ session_id, actions, finish_reason }` al cerrar. En modos Qwen, el `done` lleva `actions` con `result`.
- Toggle de dev para simular errores: `429` (rate limit), `timeout`, `unavailable`, `overloaded`, y un `event: error` mid-stream.

### 5.4 Reglas que respeta (de `apps/web/AGENTS.md`)

- **Sin cliente Supabase / sin IA externa** — todo va por `/v1/chat` y `/v1/chat/stream` (FastAPI). El streaming SSE es contra nuestro backend, nunca contra OpenAI/vLLM directo.
- **TS strict, sin `any`** — los `Record<string, unknown>` de `arguments`/`result` se tipan, no `any`. El markdown se renderiza **sanitizado** (`rehype-sanitize`), nunca `dangerouslySetInnerHTML`.
- **Tokens vía CSS variables** — burbujas y acentos usan los tints de modo existentes, nada hardcodeado.
- **TanStack Query** para no-streaming; el streaming es la excepción justificada (un stream no es una query).
- **`prefers-reduced-motion`** respetado en cursor + animaciones.

---

## 6. Arquitectura mobile

> Mobile parte de un scaffold pelado. El chat necesita **fundaciones mínimas** que hoy no existen. Esta sección las acota; el resto del onboarding/home mobile **no** es parte de este plan.

### 6.1 Fundaciones mobile que el chat necesita (prerequisito)

| Fundación | Qué incluye | Por qué la necesita el chat |
|---|---|---|
| **Design tokens (NativeWind)** | Mismos nombres de tokens que `globals.css` (tints por modo, ink, spacing). NativeWind 4 **sobre Tailwind 3** (landmine: no subir a TW4). | Burbujas, tints por modo, `ModeChip` |
| **Cliente HTTP** | `apps/mobile/src/lib/api.ts` (equivalente al web) + `env` (base URL, `EXPO_PUBLIC_*`) | `POST /v1/chat` |
| **MSW native** | `msw/native` + `@mswjs/interceptors`, init en dev | Mockear `/v1/chat(/stream)` sin backend |
| **Auth / token** | Token en `expo-secure-store` (regla mobile #5), inyectado en `api.ts` | El `/v1/chat` real pide auth (mock no) |
| **Providers** | `QueryClientProvider` + MSW init en `_layout.tsx` (hoy con TODO) | TanStack Query |

> **Decisión de scope** (§7): estas fundaciones van en una fase **mobile-foundations** propia, antes de las pantallas de chat. Si el equipo prefiere, pueden salir de un plan de "fundaciones mobile" separado y este plan solo asume que existen. Lo dejo explícito como dependencia bloqueante del track mobile.

### 6.2 Estructura de carpetas (mobile)

```
apps/mobile/src/
├── app/
│   ├── _layout.tsx                  ← MODIFICAR (providers: QueryClient + MSW + theme)
│   ├── index.tsx                    ← MODIFICAR (entrada → chat por ahora)
│   └── chat/
│       └── [sessionId].tsx          ← NUEVO (Expo Router, pantalla de conversación)
├── features/
│   └── chat/
│       ├── components/
│       │   ├── ChatScreen.tsx
│       │   ├── ChatHeader.tsx
│       │   ├── MessageList.tsx       ← FlatList (inverted / maintainVisibleContentPosition)
│       │   ├── MessageBubble.tsx     ← markdown RN-safe
│       │   ├── ActionCard.tsx
│       │   ├── ChatComposer.tsx      ← TextInput multiline + KeyboardAvoidingView
│       │   └── EmptyConversation.tsx
│       ├── hooks/
│       │   ├── useChatSession.ts
│       │   └── useChatStream.ts      ← expo/fetch + ReadableStream + parser SSE compartido
│       ├── store.ts                  ← Zustand (AsyncStorage para historial mock)
│       └── tests/
├── lib/
│   ├── api.ts                        ← NUEVO (cliente no-streaming + token de SecureStore)
│   ├── chat.ts                       ← NUEVO (stream con expo/fetch)
│   ├── env.ts                        ← NUEVO (EXPO_PUBLIC_API_URL, EXPO_PUBLIC_ENABLE_MOCKS)
│   └── api.mocks.ts                  ← NUEVO (handlers msw/native)
└── components/ui/
    └── ModeChip.tsx                  ← NUEVO (port RN del web, mismos tints)
```

### 6.3 Estado y data (mobile)

- **Store**: mismo shape de §3.5; persistencia del historial mock con `@react-native-async-storage/async-storage`. **Token** solo en `expo-secure-store`.
- **No-streaming**: TanStack Query mutation + `mobile/lib/api.ts`.
- **Streaming**: `useChatStream` con **`expo/fetch`** (`import { fetch } from "expo/fetch"`) → `response.body.getReader()` → parser SSE **compartido** (§3.4) + `AbortController`. **No** usar el `fetch` global de RN para el stream (no expone el body como stream). Spike obligatorio para validar `expo/fetch` con el wire `event:`/`data:` (§9).
- **IDs de sesión**: `crypto.randomUUID()` no existe nativo en todos los runtimes RN — usar `expo-crypto` (`randomUUID()`) o `react-native-get-random-values` + `uuid`. Generar en el handler de envío, no en render.

### 6.4 MSW (mobile)

- `msw/native` con `setupServer` + interceptors, init en `_layout.tsx` solo en dev.
- Mismos handlers conceptuales que web (`/v1/chat` JSON + `/v1/chat/stream` SSE), reusando el copy canned compartido (§3.3). **Validar** que `msw/native` soporte responses streaming SSE; si no, el handler de stream puede emular con chunks vía interceptor (spike junto al de `expo/fetch`).

### 6.5 Reglas que respeta (de `apps/mobile/AGENTS.md`)

- **Sin cliente Supabase / sin IA externa** — todo por `/v1/chat(/stream)` (FastAPI).
- **TS strict**.
- **Tokens compartidos con web** (mismos nombres), NativeWind sobre **Tailwind 3** (no subir a TW4 — landmine).
- **JWT/refresh en `expo-secure-store`**, nunca AsyncStorage.
- **Builds vía EAS** (no afecta este plan, pero submit a stores requiere OK humano).

---

## 7. Plan de ejecución

Fases con 1 PR por fase. Tres tracks: **compartido** (S0), **web** (W1–W6, reúsa lo de v1) y **mobile** (M0–M5). El track web puede arrancar apenas cierre S0; el track mobile depende de S0 + sus fundaciones.

> **Antes de cada PR**: rebasar sobre `origin/main` fresco (el doctor lo exige, check 10/10). El repo se mueve rápido — no construir sobre un `main` local desactualizado.

### 7.0 Fase S0 — Contrato + lógica compartida
**Branch**: `feat/chat-shared` · **PR**: `feat(shared): contrato del chat + parser SSE`
1. `packages/shared-schemas/src/chat.ts`: Zod mirror de `ChatRequest`, `ChatResponse`, `ChatMessage`, `Action` (con `result`), `Session`, eventos del stream. Export en el barrel.
2. `packages/shared-schemas/src/sse.ts`: parser SSE puro (chunks → eventos tipados, validados con Zod). Tests con los fixtures `apps/backend/tests/llm/fixtures/*.sse`.
3. Copy compartido: `chatErrorCopy(code)` + copy canned por modo (§3.3).
4. Tipos en `packages/shared-types` (o `z.infer` desde shared-schemas — decidir y documentar).

**Done**: schemas + parser SSE compartidos, testeados; barrel exporta todo; sin divergencia con Pydantic.

### Track web (reúsa el plan v1)

#### 7.1 Fase W1 — Infra de chat web (mock)
**Branch**: `feat/chat-web-foundations` · **PR**: `feat(web): MSW + store + cliente de chat`
1. `apps/web/src/features/chat/store.ts` (shape §3.5, persist local SSR-safe).
2. `apps/web/src/lib/chat.ts`: cliente no-streaming (`POST /v1/chat`, vía `api.post`).
3. `api.mocks.ts`: handler `/v1/chat` no-streaming, respuesta canned por modo (con `actions` solo en Qwen).
4. Smoke en `/test-mock`.

**Done**: `/v1/chat` mock devuelve un `ChatResponse` válido por modo; el store guarda la conversación.

#### 7.2 Fase W2 — Pantalla de conversación web (no-streaming)
**Branch**: `feat/chat-web-screen` · **PR**: `feat(web): pantalla de conversación`
1. Ruta `app/chat/[sessionId]/page.tsx` + dispatcher, con guards: `!onboardingCompleted` → `/onboarding`; `sessionId` inexistente → `/home` con toast "Conversación no encontrada".
2. `ChatScreen`, `ChatHeader` (ModeChip), `MessageList`, `MessageBubble`, `EmptyConversation`.
3. `ChatComposer` (textarea vivo: Enter envía, Shift+Enter newline, autosize, disabled-states, foco vuelve al enviar, límite ~4000 chars).
4. Enviar → **optimistic** → `POST /v1/chat` → render (sin streaming); si falla, no-enviado + reintentar.
5. **Markdown sanitizado** (`react-markdown` + `rehype-sanitize`, **con OK humano**).

**Done**: se manda un mensaje y se ve la respuesta del modo; estado vacío correcto; redirects correctos.

#### 7.3 Fase W3 — Streaming web (SSE)
**Branch**: `feat/chat-web-streaming` · **PR**: `feat(web): streaming de respuestas`
1. `api.mocks.ts`: handler `POST /v1/chat/stream` (SSE) con `event: token` + `event: done`.
2. `useChatStream` (fetch crudo + `ReadableStream` + parser compartido §3.4 + `AbortController`).
3. Render token-a-token con cursor; "Detener" cancela y conserva lo recibido (incompleto).
4. **Auto-scroll** + pausa al scrollear arriba (+ botón "↓ Ir al final").
5. `aria-live="polite"` en la burbuja que streamea; reduced-motion.

**Done**: respuesta token a token; cancelable; auto-scroll correcto; SR la anuncia sin spamear.

#### 7.4 Fase W4 — Actions web (modos Qwen)
**Branch**: `feat/chat-web-actions` · **PR**: `feat(web): acciones de tools (Qwen)`
1. `ActionCard` (calendar/reminder/memory; memory con diamante violeta) renderiza `name` + `arguments` + **`result`**.
2. Mock: Qwen emite `actions[]` con `result`; Gemma vacío.
3. Render de `actions[]` desde `ChatResponse` (no-streaming) y desde `event: done` (streaming).

**Done**: productividad/memoria muestran acciones; estudio/bienestar/vida no.

#### 7.5 Fase W5 — Integración home + sesiones web
**Branch**: `feat/chat-web-home` · **PR**: `feat(web): arranque desde home + historial`
1. Home: enviar desde `ChatInputDocked` o recomendación → crea sesión → navega a `/chat/[id]` con prefill.
2. `ModeSwitcher`: cambiar de modo arranca sesión nueva (confirmación si hay borrador).
3. `EmptySessions` → `SessionsList` real (mock).

**Done**: flujo home → chat completo; historial navegable.

#### 7.6 Fase W6 — Tests + a11y web
**Branch**: `feat/chat-web-tests` · **PR**: `test(web): chat — vitest + playwright + axe`
1. vitest: store, render de mensajes/acciones, lógica Qwen-vs-Gemma. (El parser SSE ya se testeó en S0.)
2. e2e: mandar → streamed response → ver; modo Qwen con acción; path de error; axe en `/chat/[id]`.
3. a11y: live region, foco, teclado; responsive 375/768/1280.

**Done**: red de tests web verde; `bash scripts/ynara-doctor.sh` exit 0.

### Track mobile

#### 7.7 Fase M0 — Fundaciones mobile (prerequisito)
**Branch**: `feat/mobile-foundations` · **PR**: `feat(mobile): tokens + providers + cliente + MSW`
1. Design tokens NativeWind (mismos nombres que `globals.css`; NativeWind 4 sobre TW3).
2. `apps/mobile/src/lib/env.ts` (`EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_ENABLE_MOCKS`).
3. `apps/mobile/src/lib/api.ts` (cliente no-streaming + token de SecureStore).
4. `msw/native` + interceptors; init en `_layout.tsx` (dev).
5. `QueryClientProvider` en `_layout.tsx`.
6. `components/ui/ModeChip.tsx` (port RN, mismos tints).

**Done**: app mobile levanta con providers + MSW; `/v1/health` mock responde; tokens visibles en un screen sandbox.

> **Spike previo (bloqueante de M2)**: validar **`expo/fetch` streaming** + **`msw/native` con SSE** con un POC mínimo contra el wire `event:`/`data:`. Si `expo/fetch` no alcanza, fallback `react-native-sse`. Documentar el resultado en este doc antes de M2.

#### 7.8 Fase M1 — Pantalla de conversación mobile (no-streaming)
**Branch**: `feat/chat-mobile-screen` · **PR**: `feat(mobile): pantalla de conversación`
1. Ruta `app/chat/[sessionId].tsx` (Expo Router).
2. `ChatScreen`, `ChatHeader`, `MessageList` (FlatList), `MessageBubble`, `EmptyConversation`.
3. `ChatComposer` (`TextInput multiline` + `KeyboardAvoidingView`).
4. Store mobile (§6.3) + `lib/chat.ts` no-streaming + handler MSW `/v1/chat`.
5. Enviar → optimistic → `POST /v1/chat` → render; si falla, reintentar.
6. **Markdown RN-safe** (`react-native-markdown-display` u otra, **con OK humano**; validar subset y seguridad).

**Done**: en mobile se manda un mensaje y se ve la respuesta del modo; estado vacío correcto.

#### 7.9 Fase M2 — Streaming mobile (SSE con expo/fetch)
**Branch**: `feat/chat-mobile-streaming` · **PR**: `feat(mobile): streaming de respuestas`
1. Handler MSW `/v1/chat/stream` (o emulación de chunks si `msw/native` no streamea — según spike M0).
2. `useChatStream` con `expo/fetch` + `ReadableStream` + parser compartido + `AbortController`.
3. Render token-a-token con cursor; "Detener" cancela y conserva lo recibido.
4. Auto-scroll en FlatList (inverted / `maintainVisibleContentPosition`).
5. `accessibilityLiveRegion="polite"`; reduced-motion vía `AccessibilityInfo`.

**Done**: respuesta token a token en mobile; cancelable; auto-scroll correcto.

#### 7.10 Fase M3 — Actions mobile (modos Qwen)
**Branch**: `feat/chat-mobile-actions` · **PR**: `feat(mobile): acciones de tools (Qwen)`
1. `ActionCard` RN (calendar/reminder/memory; memory con diamante violeta) con `arguments` + `result`.
2. Render de `actions[]` desde no-streaming y `event: done`.

**Done**: paridad de actions con web; Gemma sin acciones.

#### 7.11 Fase M4 — Sesiones mobile (slice liviano)
**Branch**: `feat/chat-mobile-sessions` · **PR**: `feat(mobile): historial de sesiones`
1. Lista de sesiones (mock, AsyncStorage) + retomar conversación.
2. `ModeSwitcher` mobile: cambiar de modo = sesión nueva.

**Done**: historial navegable en mobile.

> **Nota**: el "arranque desde home" (equivalente a W5) en mobile depende de que exista una home mobile, que **no** es parte de este plan. M4 entrega sesiones standalone; la integración con una futura home mobile queda como follow-up.

#### 7.12 Fase M5 — Tests + a11y mobile
**Branch**: `feat/chat-mobile-tests` · **PR**: `test(mobile): chat — RNTL + a11y`
1. React Native Testing Library: store, render de mensajes/acciones, Qwen-vs-Gemma.
2. a11y: live region, foco del teclado, labels; reduced-motion.

**Done**: red de tests mobile verde; doctor exit 0.

### 7.13 Estrategia de PRs

| # | PR | Branch | Track | Tamaño | Reviewer |
|---|---|---|---|---|---|
| S0 | `feat(shared): contrato del chat + parser SSE` | `feat/chat-shared` | shared | M | @BriarDevv (contrato) |
| W1 | `feat(web): MSW + store + cliente de chat` | `feat/chat-web-foundations` | web | M | @BriarDevv |
| W2 | `feat(web): pantalla de conversación` | `feat/chat-web-screen` | web | L | @querques20 (UX) |
| W3 | `feat(web): streaming de respuestas` | `feat/chat-web-streaming` | web | M | @BriarDevv |
| W4 | `feat(web): acciones de tools (Qwen)` | `feat/chat-web-actions` | web | M | @querques20 |
| W5 | `feat(web): arranque desde home + historial` | `feat/chat-web-home` | web | M | @querques20 |
| W6 | `test(web): chat — vitest + playwright + axe` | `feat/chat-web-tests` | web | M | @BriarDevv |
| M0 | `feat(mobile): tokens + providers + cliente + MSW` | `feat/mobile-foundations` | mobile | L | @BriarDevv |
| M1 | `feat(mobile): pantalla de conversación` | `feat/chat-mobile-screen` | mobile | L | @querques20 |
| M2 | `feat(mobile): streaming de respuestas` | `feat/chat-mobile-streaming` | mobile | M | @BriarDevv |
| M3 | `feat(mobile): acciones de tools (Qwen)` | `feat/chat-mobile-actions` | mobile | M | @querques20 |
| M4 | `feat(mobile): historial de sesiones` | `feat/chat-mobile-sessions` | mobile | M | @querques20 |
| M5 | `test(mobile): chat — RNTL + a11y` | `feat/chat-mobile-tests` | mobile | M | @BriarDevv |

**Cortes naturales**:
- **Web**: tras W4 el chat web ya es usable de punta a punta con streaming + acciones; W5 (home) y W6 (tests) se pueden diferir si aprieta.
- **Mobile**: depende de M0 (fundaciones) + spike de streaming. Si el spike de `expo/fetch`/`msw native` traba, M1 (no-streaming) se puede shippear igual y M2 espera.
- **Secuencia recomendada**: S0 → track web completo (es más barato, reúsa todo) → track mobile. No paralelizar web y mobile si el equipo es chico: que el track web valide el contrato compartido antes de que mobile lo consuma.

---

## 8. Definition of Done

### Repo / proceso
- [ ] S0 + track elegido mergeados a `main` (rebasados sobre `origin/main` fresco; doctor exit 0 en cada PR).
- [ ] Sin `any`, sin `@ts-ignore` sin justificación. Sin `@supabase/supabase-js`, sin `openai/anthropic/google-genai` (web y mobile).
- [ ] Zod del chat = mirror de `app/llm/schemas.py` (sin divergencia silenciosa); schemas y parser SSE **compartidos**, no duplicados.

### Chat funcional (web)
- [ ] Mandar un mensaje (`POST /v1/chat`) y recibir respuesta del modo activo.
- [ ] Streaming (`POST /v1/chat/stream`, eventos `token`/`done`/`error`) token-a-token con cursor; cancelable.
- [ ] Respuestas con **markdown sanitizado**, sin HTML crudo.
- [ ] Modos Qwen muestran `actions[]` con `result`; modos Gemma no.
- [ ] Errores humanos por tipo (timeout/unavailable/overloaded/429), con reintento.
- [ ] Cambiar de modo arranca sesión nueva; home arranca sesión; historial navegable.

### Chat funcional (mobile)
- [ ] Fundaciones M0 (tokens, providers, cliente, MSW, SecureStore) en su lugar.
- [ ] Spike de `expo/fetch` + `msw/native` SSE documentado en este doc.
- [ ] Mandar mensaje y recibir respuesta del modo (no-streaming) en mobile.
- [ ] Streaming token-a-token con `expo/fetch`; cancelable.
- [ ] Markdown RN-safe; actions de Qwen; Gemma sin acciones.
- [ ] Historial de sesiones (mock) navegable.

### A11y
- [ ] **[web]** `aria-live` en la respuesta que streamea; Tab/Enter/Shift+Enter coherentes; foco gestionado; axe sin violations críticas en `/chat/[id]`.
- [ ] **[mobile]** `accessibilityLiveRegion` en la respuesta; labels en botones; foco de teclado correcto.
- [ ] `prefers-reduced-motion` / `AccessibilityInfo` respetado (cursor + animaciones) en ambas.

### Responsive / dispositivos
- [ ] **[web]** 375 / 768 / 1280 verificado (screenshots en el PR).
- [ ] **[mobile]** verificado en al menos un iOS y un Android (o simuladores), teclado no tapa el composer.

---

## 9. Riesgos y landmines

> El contrato del chat quedó **cerrado** por @BriarDevv en [`RESPUESTAS-CONTRATO-CHAT.md`](./RESPUESTAS-CONTRATO-CHAT.md) (PR #61): streaming en `/v1/chat/stream` con eventos `token`/`done`/`error`, `Action` con `result`, `actions` siempre presente, markdown sí, límite ~4000 chars. Las preguntas de la antigua §7.1 ya no están abiertas (ver §9.1 abajo).

**[mobile, crítico] Streaming SSE en React Native.** El `fetch` global de RN **no** expone `response.body` como `ReadableStream` — devuelve el body entero, lo que rompe el token-a-token. Solución recomendada: **`expo/fetch`** (Expo 53, fetch WinterCG con streaming). Fallback: `react-native-sse` o XHR `onprogress`. **Hacer un spike antes de M2** (parte de M0) y documentar el resultado acá. No asumir que el `useChatStream` del web corre tal cual en mobile.

**[mobile] `msw/native` y SSE.** MSW corre en RN vía `msw/native`, pero la emulación de respuestas **streaming** SSE puede no ser directa. Validar en el mismo spike; si no soporta, el handler de stream mobile emula chunks vía interceptor.

**[mobile] No hay design system mobile.** El onboarding fue web-only; mobile es scaffold. Los tints por modo y tokens hay que **portarlos** a NativeWind con los mismos nombres que `globals.css`. NativeWind 4 corre **sobre Tailwind 3** — no subir a TW4 (landmine del repo).

**[mobile] `crypto.randomUUID` no es nativo.** Usar `expo-crypto` (`randomUUID`) o `react-native-get-random-values`. Generar el id en el handler de envío.

**[mobile] Token solo en SecureStore.** JWT/refresh en `expo-secure-store` (regla mobile #5), nunca AsyncStorage. El historial mock sí puede ir en AsyncStorage (no es secreto).

**Auth es prerequisito del backend real, no del mock.** `core/security.py` ya se implementó (#62), pero el `/v1/chat` real todavía no existe ni está cableado a auth. El mock no exige auth. Cuando se conecte al backend real, hace falta: (a) M9 (endpoint), (b) la inyección de `Authorization: Bearer <token>` en `lib/api.ts` de cada plataforma (hoy un TODO). Sin eso, el chat real devuelve 401.

**Pydantic gana, Zod sigue.** Los Zod del chat son mirror de `app/llm/schemas.py`. Si el backend toca esos schemas, corregir el mirror en el mismo PR. Ventaja: el Pydantic **ya existe**, así que la divergencia es detectable desde el día 1.

**Una sesión = un modo.** No re-etiquetar la conversación al cambiar de modo: arrancar sesión nueva (coherente con `SessionOut.mode`).

**Streaming no es una query.** Usar TanStack Query para el caso no-streaming, pero el stream va con `fetch`/`expo/fetch` + `ReadableStream` + `AbortController` en `useChatStream`. No forzar el stream dentro de Query.

**[web] Storage de zustand SSR-safe.** Persist local con storage **no-op en server** (`StateStorage`), no `undefined` (la factory de zustand 5.0.13 no lo acepta — landmine del onboarding).

**El frontend no toca memoria.** La memoria (semantic/episodic/procedural) la maneja el backend async vía Celery, fuera del path de respuesta. El frontend solo **muestra** confirmaciones de memoria que vengan en `actions[]`; no escribe ni lee memoria directo.

**No persistir "de verdad".** El mock guarda sesiones/mensajes local; cuando exista el backend, la persistencia es de él. Cuando el backend reemplace el mock, las sesiones locales se pierden (no hay migración) — aceptable para MVP, anotarlo en el PR.

**Rate limiting.** `ENDPOINTS.md` prevé ~30/min por usuario (TODO del backend). El mock debe poder simular un `429` para probar la UX de cooldown. No construir un rate-limiter real en el cliente.

**No mover componentes a `packages/ui` por reflejo.** La capa compartida de este plan es **data/lógica** (`packages/shared-schemas`), no componentes. Compartir componentes RN-compatibles en `packages/ui` es una decisión aparte (hoy ese package está vacío a propósito).

### 9.1 Decisiones cerradas (eran preguntas abiertas)

Cerradas por @BriarDevv en [`RESPUESTAS-CONTRATO-CHAT.md`](./RESPUESTAS-CONTRATO-CHAT.md) (PR #61) + decisión del owner:

| # | Pregunta | Decisión |
|---|---|---|
| 1 | ¿Streaming por content-negotiation o endpoint aparte? | **Endpoint aparte `POST /v1/chat/stream`** (SSE). `/v1/chat` queda no-streaming. |
| 2 | ¿Shape del evento terminal? | **Eventos SSE con nombre**: `token {delta}`, `done {session_id, actions, finish_reason}`, `error {code, message}`. |
| 3 | ¿`actions[]` con `result`? | **Sí**: `Action = { id, name, arguments, result }`. |
| 4 | ¿`actions?` o `actions: Action[]`? | **`actions: Action[]`** (siempre presente). Ya corregido en `ENDPOINTS.md`. |
| 5 | ¿Markdown en las respuestas? | **Sí**, subset seguro sanitizado desde el MVP (owner). |
| 6 | ¿Máximo de longitud del mensaje? | **~4.000 chars** (techo seguro contra el `max_model_len` de Gemma). |

### 9.2 Decisiones mobile a validar (spike M0)

| # | Pregunta | Estado |
|---|---|---|
| 1 | ¿`expo/fetch` streamea SSE con `event:`/`data:` en iOS y Android? | **A validar** (recomendado sí; fallback `react-native-sse`) |
| 2 | ¿`msw/native` emula responses SSE streaming? | **A validar** (fallback: emular chunks por interceptor) |
| 3 | ¿Lib de markdown RN segura para el subset? | **A validar** (`react-native-markdown-display` candidata) |
| 4 | ¿La home/onboarding mobile existe para integrar el arranque del chat? | **No** — fuera de scope; M4 entrega sesiones standalone |

---

## 10. Referencias cruzadas

- [`AGENTS.md`](../../AGENTS.md) — 10 reglas no negociables (#4 sin IA externa, #5 sin Supabase en frontend).
- [`apps/web/AGENTS.md`](../../apps/web/AGENTS.md) — reglas duras del frontend web.
- [`apps/mobile/AGENTS.md`](../../apps/mobile/AGENTS.md) — reglas duras del frontend mobile (SecureStore, NativeWind sobre TW3).
- [`apps/backend/app/llm/schemas.py`](../../apps/backend/app/llm/schemas.py) — **contrato fuente** (ChatRequest/Response, ChatMessage, ToolCall, CompletionChunk).
- [`docs/planning/RESPUESTAS-CONTRATO-CHAT.md`](./RESPUESTAS-CONTRATO-CHAT.md) — **respuestas de contrato cerradas** (@BriarDevv, PR #61): streaming, eventos, `Action.result`, markdown, límite.
- [`apps/backend/docs/ENDPOINTS.md`](../../apps/backend/docs/ENDPOINTS.md) — spec de `POST /v1/chat` + `POST /v1/chat/stream` (M9).
- [`docs/planning/LLM-INFERENCE-INTEGRATION.md`](./LLM-INFERENCE-INTEGRATION.md) — milestones del backend LLM (M8 router, M9 endpoint).
- [`docs/product/MODES.md`](../product/MODES.md) — definición + tono de los 5 modos.
- [`docs/architecture/adrs/ADR-002-gemma-qwen-dual-stack.md`](../architecture/adrs/ADR-002-gemma-qwen-dual-stack.md) — Gemma lee / Qwen escribe + tools.
- [`ynara.config.json`](../../ynara.config.json) — config canónica de modos.
- [`docs/planning/archive/FRONTEND-ONBOARDING-PLAN.md`](./archive/FRONTEND-ONBOARDING-PLAN.md) — el slice anterior (ejecutado, web), mismo formato.

---

> **Cómo usar este documento**: cada fase arranca con un PR scope claro y termina con un Done explícito. El track web es incremental; el mobile arrastra el prerequisito de fundaciones (M0) + un spike de streaming. Si cambia el scope o el contrato del backend, editar este doc en el mismo PR. Cuando todas las fases del track cierren, marcar como "ejecutado" y mover a `docs/planning/archive/`.
