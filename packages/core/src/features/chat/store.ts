import type { Action, ChatResponse, Mode } from "@ynara/shared-schemas";
import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

/**
 * Store de conversación del chat, compartido web + mobile (ADR-012).
 * Mapa de sesiones + mensajes por sesión + estado de streaming.
 *
 * El storage del `persist` se inyecta (web: localStorage; mobile: SecureStore).
 * Persistencia local (mock) hasta que el backend (M9) sea la fuente.
 * `streamStatus` es efímero: no se persiste.
 */

/**
 * Estado de un mensaje individual en la UI.
 *
 * `degraded`: turno en el que la IA NO estuvo disponible (`finish_reason ===
 * "degraded"`, ADR-027). El backend degrada a 200 con un texto enlatado; el
 * front lo DESCARTA y muestra un estado honesto "IA no disponible" (ver
 * `chatPausedCopy`). Es terminal y NO es `error`: el turno del usuario no falló,
 * la IA está pausada/caída.
 */
export type ChatMessageStatus =
  | "sending"
  | "streaming"
  | "done"
  | "error"
  | "degraded"
  | "canceled";

/** Un mensaje de la conversación tal como lo renderiza la UI. */
export type ChatUiMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  status: ChatMessageStatus;
  /** Solo en mensajes de assistant de modos Qwen. */
  actions?: Action[];
  /** Código del error del backend (mapea a copy humano) si status==="error". */
  errorCode?: string;
  /**
   * Razonamiento post-hoc del modelo (evento SSE `reasoning`), acumulado token
   * a token. EFÍMERO: se recibe por stream y se EXCLUYE de la persistencia
   * (`partialize`) para no inflar localStorage con cadenas largas. El front lo
   * muestra (colapsable "Pensando…") solo si el toggle web está ON.
   */
  reasoning?: string;
};

/** Metadata de una sesión (una sesión = un modo). */
export type ChatSessionMeta = {
  id: string;
  mode: Mode;
  createdAt: number;
  updatedAt: number;
};

export type ChatStreamStatus = "idle" | "streaming" | "error";

type ChatState = {
  sessions: Record<string, ChatSessionMeta>;
  messages: Record<string, ChatUiMessage[]>;
  streamStatus: ChatStreamStatus;
};

type ChatActions = {
  /** Crea una sesión nueva en el modo dado y devuelve su id. */
  createSession: (mode: Mode) => string;
  /** Agrega un mensaje del usuario (optimistic, status "sending"). */
  appendUserMessage: (sessionId: string, text: string) => string;
  /** Agrega un mensaje del assistant ya completo (no-streaming). */
  appendAssistantMessage: (
    sessionId: string,
    message: { text: string; actions?: Action[]; status?: ChatMessageStatus },
  ) => string;
  /** Cambia el status de un mensaje (p. ej. "sending" → "done"/"error"). */
  setMessageStatus: (
    sessionId: string,
    messageId: string,
    status: ChatMessageStatus,
    errorCode?: string,
  ) => void;
  /**
   * Cierra el ciclo optimistic no-streaming en una sola transición: marca el
   * mensaje del usuario (`userMessageId`, hoy "sending") como "done" y agrega
   * la respuesta del assistant. Atómico para que la UI no vea estados
   * intermedios ni mensajes colgados en "sending".
   */
  applyChatResponse: (sessionId: string, userMessageId: string, response: ChatResponse) => void;
  setStreamStatus: (status: ChatStreamStatus) => void;
  /**
   * Abre un stream del assistant en UNA transición atómica (espejo de
   * `applyChatResponse`): cierra el mensaje del usuario (`userMessageId`,
   * hoy "sending") como "done", agrega un mensaje de assistant vacío en
   * "streaming", marca `streamStatus:"streaming"` y toca `updatedAt`.
   * Devuelve el id del mensaje de assistant nuevo (el destino de los deltas).
   */
  startAssistantStream: (sessionId: string, userMessageId: string) => string;
  /** Concatena un delta al texto del mensaje de assistant en curso (corre por token). */
  appendStreamDelta: (sessionId: string, assistantId: string, delta: string) => void;
  /**
   * Concatena un delta al RAZONAMIENTO del assistant en curso (espejo de
   * `appendStreamDelta`, corre por cada evento `reasoning`). Acumula en
   * `m.reasoning` sin tocar `m.text`. Efímero: no se persiste (ver partialize).
   */
  appendReasoningDelta: (sessionId: string, assistantId: string, delta: string) => void;
  /**
   * Cierra el stream: assistant "streaming" → "done", adjunta `actions` si hay,
   * `streamStatus:"idle"` y toca `updatedAt`.
   *
   * `finishReason` viene del evento `done` del SSE. Si es `"degraded"` (ADR-027,
   * IA no disponible), el mensaje queda `status:"degraded"` con el texto enlatado
   * DESCARTADO (la UI muestra un estado honesto), no `"done"`.
   */
  finishAssistantStream: (
    sessionId: string,
    assistantId: string,
    opts?: { actions?: Action[]; finishReason?: string | null },
  ) => void;
  /**
   * Cierra el stream con error. `streamStatus:"error"`. Para que el retry
   * existente siga funcionando (el botón "Reintentar" sale solo en un mensaje
   * `role==="user" && status==="error"`, ver MessageList), marca SIEMPRE el
   * mensaje del usuario como "error". Decisión sobre el placeholder del
   * assistant: si NO llegó ningún token (texto vacío) se descarta el
   * placeholder colgado; si ya llegó texto parcial se conserva ese parcial
   * marcado "error" (no se pierde lo que el usuario alcanzó a leer).
   */
  failAssistantStream: (sessionId: string, assistantId: string, errorCode?: string) => void;
  /**
   * Cancela el stream (path del AbortController): si llegó texto parcial, el
   * mensaje del assistant queda "canceled" conservándolo; si NO llegó ningún
   * token, se descarta el placeholder vacío (mismo criterio que
   * `failAssistantStream`, para no dejar una burbuja vacía y muda).
   * `streamStatus:"idle"`.
   */
  cancelAssistantStream: (sessionId: string, assistantId: string) => void;
  reset: () => void;
};

const initialState: ChatState = {
  sessions: {},
  messages: {},
  streamStatus: "idle",
};

/**
 * UUID SSR-safe: solo se llama desde handlers de cliente, nunca en render.
 *
 * Usa `crypto.randomUUID` cuando está disponible, pero cae a un v4 armado con
 * `crypto.getRandomValues` cuando NO lo está: `randomUUID` solo existe en
 * *secure contexts* (https:// o localhost), así que sobre `http://` por una IP de
 * LAN/Tailscale (ej. el amigo entrando por `100.x.x.x:3000`) sería `undefined` y
 * el chat rompería al crear sesión. `getRandomValues` sí está en contextos
 * no-seguros, así que el fallback mantiene el chat funcional en ese escenario.
 */
function newId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  // `byte` del forEach es `number` (no `number | undefined`), así esto no choca con
  // `noUncheckedIndexedAccess`. v4: version (0100) en el byte 6; variant (10) en el 8.
  const hex: string[] = [];
  bytes.forEach((byte, i) => {
    let b = byte;
    if (i === 6) b = (b & 0x0f) | 0x40;
    if (i === 8) b = (b & 0x3f) | 0x80;
    hex.push(b.toString(16).padStart(2, "0"));
  });
  return (
    `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}` +
    `-${hex.slice(8, 10).join("")}-${hex.slice(10, 16).join("")}`
  );
}

/**
 * Crea el store de chat sobre el `storage` provisto. Cada app lo instancia una
 * vez con el storage de su plataforma.
 */
export function createChatStore(storage: StateStorage) {
  return create<ChatState & ChatActions>()(
    persist(
      (set) => ({
        ...initialState,

        createSession: (mode) => {
          const id = newId();
          const now = Date.now();
          set((s) => ({
            sessions: { ...s.sessions, [id]: { id, mode, createdAt: now, updatedAt: now } },
            messages: { ...s.messages, [id]: [] },
            // Sesión nueva arranca sin stream en curso (relevante en streaming,
            // cuando un stream anterior podría quedar "streaming").
            streamStatus: "idle",
          }));
          return id;
        },

        appendUserMessage: (sessionId, text) => {
          const id = newId();
          set((s) => appendMessage(s, sessionId, { id, role: "user", text, status: "sending" }));
          return id;
        },

        appendAssistantMessage: (sessionId, message) => {
          const id = newId();
          set((s) =>
            appendMessage(s, sessionId, {
              id,
              role: "assistant",
              text: message.text,
              status: message.status ?? "done",
              actions: message.actions,
            }),
          );
          return id;
        },

        setMessageStatus: (sessionId, messageId, status, errorCode) =>
          set((s) => {
            const list = s.messages[sessionId];
            if (!list) return s;
            return {
              messages: {
                ...s.messages,
                [sessionId]: list.map((m) =>
                  m.id === messageId ? { ...m, status, errorCode } : m,
                ),
              },
            };
          }),

        applyChatResponse: (sessionId, userMessageId, response) =>
          set((s) => {
            const list = s.messages[sessionId];
            if (!list) return s;
            // 1) Cerrar el mensaje optimistic del usuario (sending → done).
            const userClosed = list.map((m) =>
              m.id === userMessageId ? { ...m, status: "done" as const } : m,
            );
            // 2) Agregar la respuesta del assistant. Paridad con el streaming
            //    (finishAssistantStream): finish_reason="degraded" (ADR-027) => IA
            //    no disponible; descartamos el texto enlatado y marcamos el turno
            //    "degraded" (estado honesto), no "done".
            const degraded = response.finish_reason === "degraded";
            const assistant: ChatUiMessage = {
              id: newId(),
              role: "assistant",
              text: degraded ? "" : response.text,
              status: degraded ? "degraded" : "done",
              actions: !degraded && response.actions.length > 0 ? response.actions : undefined,
            };
            const session = s.sessions[sessionId];
            return {
              messages: { ...s.messages, [sessionId]: [...userClosed, assistant] },
              sessions: session
                ? { ...s.sessions, [sessionId]: { ...session, updatedAt: Date.now() } }
                : s.sessions,
            };
          }),

        setStreamStatus: (streamStatus) => set({ streamStatus }),

        startAssistantStream: (sessionId, userMessageId) => {
          const assistantId = newId();
          set((s) => {
            const list = s.messages[sessionId];
            if (!list) return s;
            // 1) Cerrar el optimistic del usuario (sending → done).
            const userClosed = list.map((m) =>
              m.id === userMessageId ? { ...m, status: "done" as const } : m,
            );
            // 2) Placeholder de assistant en "streaming" (texto vacío). Se crea
            //    de entrada para que la UI muestre la respuesta en curso de
            //    inmediato (affordance optimista), antes del primer token.
            const assistant: ChatUiMessage = {
              id: assistantId,
              role: "assistant",
              text: "",
              // Razonamiento arranca vacío: si el modelo razona, los eventos
              // `reasoning` lo van llenando vía appendReasoningDelta (efímero).
              reasoning: "",
              status: "streaming",
            };
            const session = s.sessions[sessionId];
            return {
              messages: { ...s.messages, [sessionId]: [...userClosed, assistant] },
              sessions: session
                ? { ...s.sessions, [sessionId]: { ...session, updatedAt: Date.now() } }
                : s.sessions,
              streamStatus: "streaming",
            };
          });
          return assistantId;
        },

        appendStreamDelta: (sessionId, assistantId, delta) =>
          set((s) => {
            const list = s.messages[sessionId];
            if (!list) return s;
            return {
              messages: {
                ...s.messages,
                [sessionId]: list.map((m) =>
                  m.id === assistantId ? { ...m, text: m.text + delta } : m,
                ),
              },
            };
          }),

        appendReasoningDelta: (sessionId, assistantId, delta) =>
          set((s) => {
            const list = s.messages[sessionId];
            if (!list) return s;
            return {
              messages: {
                ...s.messages,
                [sessionId]: list.map((m) =>
                  m.id === assistantId ? { ...m, reasoning: (m.reasoning ?? "") + delta } : m,
                ),
              },
            };
          }),

        finishAssistantStream: (sessionId, assistantId, opts) =>
          set((s) => {
            const list = s.messages[sessionId];
            if (!list) return s;
            const actions = opts?.actions;
            // finish_reason="degraded" (ADR-027): la IA no estuvo disponible. El
            // backend ya devolvió 200 con un texto enlatado (que durante el
            // stream se acumuló en m.text); lo DESCARTAMOS —parece una respuesta
            // real y sería mentira— y marcamos el turno "degraded" para que la UI
            // muestre un estado honesto. No es "error": el turno del user no
            // falló, la IA está pausada/caída.
            // Micro-flicker aceptado (fase 1a): si el transporte entrega el texto
            // enlatado y el `done` en reads separados, puede pintarse 1 frame del
            // enlatado antes de que este descarte lo borre. El buffering fino (no
            // pintar hasta el done) queda para una fase posterior.
            const degraded = opts?.finishReason === "degraded";
            const closed = list.map((m) => {
              if (m.id !== assistantId) return m;
              if (degraded) {
                return { ...m, status: "degraded" as const, text: "", actions: undefined };
              }
              return {
                ...m,
                status: "done" as const,
                actions: actions && actions.length > 0 ? actions : m.actions,
              };
            });
            const session = s.sessions[sessionId];
            return {
              messages: { ...s.messages, [sessionId]: closed },
              sessions: session
                ? { ...s.sessions, [sessionId]: { ...session, updatedAt: Date.now() } }
                : s.sessions,
              streamStatus: "idle",
            };
          }),

        failAssistantStream: (sessionId, assistantId, errorCode) =>
          set((s) => {
            const list = s.messages[sessionId];
            if (!list) return s;
            const assistantIdx = list.findIndex((m) => m.id === assistantId);
            const assistant = assistantIdx === -1 ? undefined : list[assistantIdx];
            const hasPartial = (assistant?.text.length ?? 0) > 0;
            // El user del turno que falló es el `role==="user"` más cercano ANTES
            // del placeholder de assistant —NO el "último user" global. Con varios
            // turnos en la sesión, "último user" podría marcar el turno equivocado;
            // anclar al assistant del stream lo vuelve correcto. Lo resolvemos a un
            // id (no a un índice) porque `trimmed` puede descartar el placeholder y
            // correr los índices.
            let turnUserId: string | undefined;
            for (let i = assistantIdx - 1; i >= 0; i--) {
              if (list[i]?.role === "user") {
                turnUserId = list[i]?.id;
                break;
              }
            }
            // Si NO llegó texto, descartamos el placeholder vacío del assistant
            // (no tiene nada que mostrar). Si llegó parcial, lo conservamos
            // marcado "error" (no se pierde lo que el usuario alcanzó a leer).
            const trimmed = hasPartial
              ? list.map((m) =>
                  m.id === assistantId ? { ...m, status: "error" as const, errorCode } : m,
                )
              : list.filter((m) => m.id !== assistantId);
            // Marcamos el user del turno "error" (startAssistantStream lo había
            // cerrado en "done"), así el retry de MessageList (user + error)
            // reaparece y se puede reintentar el envío.
            const withUserError =
              turnUserId === undefined
                ? trimmed
                : trimmed.map((m) =>
                    m.id === turnUserId ? { ...m, status: "error" as const, errorCode } : m,
                  );
            const session = s.sessions[sessionId];
            return {
              messages: { ...s.messages, [sessionId]: withUserError },
              sessions: session
                ? { ...s.sessions, [sessionId]: { ...session, updatedAt: Date.now() } }
                : s.sessions,
              streamStatus: "error",
            };
          }),

        cancelAssistantStream: (sessionId, assistantId) =>
          set((s) => {
            const list = s.messages[sessionId];
            if (!list) return s;
            const assistant = list.find((m) => m.id === assistantId);
            const hasPartial = (assistant?.text.length ?? 0) > 0;
            // Con parcial: lo conservamos marcado "canceled". Sin ningún token:
            // descartamos el placeholder vacío (si no, queda una burbuja vacía y
            // muda en la conversación). Mismo criterio que failAssistantStream.
            const next = hasPartial
              ? list.map((m) => (m.id === assistantId ? { ...m, status: "canceled" as const } : m))
              : list.filter((m) => m.id !== assistantId);
            const session = s.sessions[sessionId];
            return {
              messages: { ...s.messages, [sessionId]: next },
              sessions: session
                ? { ...s.sessions, [sessionId]: { ...session, updatedAt: Date.now() } }
                : s.sessions,
              streamStatus: "idle",
            };
          }),

        reset: () => set(initialState),
      }),
      {
        name: "ynara.chat",
        storage: createJSONStorage(() => storage),
        // streamStatus es efímero: se omite de la persistencia (al rehidratar
        // toma su valor inicial "idle" de initialState), no se escribe a disco.
        // `reasoning` también se excluye por mensaje (`stripReasoning`): es
        // efímero (se recibe por stream) y puede ser largo — no inflamos el
        // localStorage con la cadena de pensamiento.
        partialize: (s) => ({
          sessions: s.sessions,
          messages: Object.fromEntries(
            Object.entries(s.messages).map(([sid, list]) => [sid, list.map(stripReasoning)]),
          ),
        }),
        // Reconciliación post-rehidratación: si la app se cerró/crasheó con un
        // stream en vuelo, el status del mensaje (que vive en `messages`, SÍ
        // persistido) quedó en "streaming"/"sending". `streamStatus` se resetea a
        // "idle", pero el status del mensaje no, así que sin esto el bubble queda
        // colgado (un spinner que nunca cierra) y, peor, el user en "done" no
        // muestra "Reintentar". Bajamos esos estados huérfanos a uno terminal: el
        // assistant con parcial → "error" (se conserva lo leído), el placeholder
        // vacío se descarta, y el user → "error" (rehabilita el retry).
        onRehydrateStorage: () => (state) => {
          if (!state) return;
          for (const [sid, list] of Object.entries(state.messages)) {
            state.messages[sid] = list
              .filter((m) => !(m.role === "assistant" && m.status === "streaming" && m.text === ""))
              .map((m) =>
                m.status === "streaming" || m.status === "sending"
                  ? { ...m, status: "error" as const }
                  : m,
              );
          }
        },
      },
    ),
  );
}

/**
 * Devuelve una copia del mensaje SIN `reasoning` (para la persistencia). Si el
 * mensaje no tiene `reasoning`, lo devuelve tal cual (sin copia innecesaria).
 * Inmutable: nunca muta el mensaje original del store.
 */
function stripReasoning(message: ChatUiMessage): ChatUiMessage {
  if (message.reasoning === undefined) return message;
  const copy = { ...message };
  copy.reasoning = undefined;
  return copy;
}

/** Agrega un mensaje a una sesión y toca su `updatedAt` (usa `Date.now()`). */
function appendMessage(
  state: ChatState,
  sessionId: string,
  message: ChatUiMessage,
): Pick<ChatState, "messages" | "sessions"> {
  const list = state.messages[sessionId] ?? [];
  const session = state.sessions[sessionId];
  return {
    messages: { ...state.messages, [sessionId]: [...list, message] },
    sessions: session
      ? { ...state.sessions, [sessionId]: { ...session, updatedAt: Date.now() } }
      : state.sessions,
  };
}
