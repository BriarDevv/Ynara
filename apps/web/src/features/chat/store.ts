import type { Action, ChatResponse } from "@ynara/shared-schemas";
import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";
import type { ModeId } from "@/components/ui/modes";

/**
 * Store de conversación del chat (web). Implementa el shape compartido del
 * plan §3.5: mapa de sesiones + mensajes por sesión + estado de streaming.
 *
 * Persistencia local (mock) en `localStorage`: cuando exista el backend (M9),
 * la persistencia es de él y las sesiones locales se pierden (sin migración,
 * aceptable para MVP — ver landmine del plan). El streaming llega en W3; acá
 * `streamStatus` existe pero el flujo no-streaming solo usa `idle`.
 */

/** Estado de un mensaje individual en la UI. */
export type ChatMessageStatus = "sending" | "streaming" | "done" | "error" | "canceled";

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
};

/** Metadata de una sesión (una sesión = un modo, plan §2.3). */
export type ChatSessionMeta = {
  id: string;
  mode: ModeId;
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
  createSession: (mode: ModeId) => string;
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
   * Cierra el stream OK: assistant "streaming" → "done", adjunta `actions`
   * si hay, `streamStatus:"idle"` y toca `updatedAt`.
   */
  finishAssistantStream: (
    sessionId: string,
    assistantId: string,
    opts?: { actions?: Action[] },
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
   * Cancela el stream (path del AbortController): el mensaje del assistant
   * queda "canceled" conservando el parcial que haya llegado, `streamStatus:"idle"`.
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
 * `localStorage` con guard SSR: en server no existe. La factory de zustand
 * 5.0.13 tipa el retorno como `StateStorage` (no acepta `undefined`), así que
 * devolvemos un storage no-op en server (mismo patrón que el store del
 * onboarding). `streamStatus` no se persiste: es estado efímero de runtime.
 */
const noopStorage: StateStorage = {
  getItem: () => null,
  removeItem: () => undefined,
  setItem: () => undefined,
};

const localJsonStorage = createJSONStorage(() =>
  typeof window === "undefined" ? noopStorage : localStorage,
);

/** UUID SSR-safe: solo se llama desde handlers de cliente, nunca en render. */
function newId(): string {
  return crypto.randomUUID();
}

export const useChatStore = create<ChatState & ChatActions>()(
  persist(
    (set) => ({
      ...initialState,

      createSession: (mode) => {
        const id = newId();
        const now = Date.now();
        set((s) => ({
          sessions: { ...s.sessions, [id]: { id, mode, createdAt: now, updatedAt: now } },
          messages: { ...s.messages, [id]: [] },
          // Sesión nueva arranca sin stream en curso (relevante en W3, cuando
          // un stream anterior podría quedar "streaming").
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
              [sessionId]: list.map((m) => (m.id === messageId ? { ...m, status, errorCode } : m)),
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
          // 2) Agregar la respuesta del assistant.
          const assistant: ChatUiMessage = {
            id: newId(),
            role: "assistant",
            text: response.text,
            status: "done",
            actions: response.actions.length > 0 ? response.actions : undefined,
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

      finishAssistantStream: (sessionId, assistantId, opts) =>
        set((s) => {
          const list = s.messages[sessionId];
          if (!list) return s;
          const actions = opts?.actions;
          const closed = list.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  status: "done" as const,
                  actions: actions && actions.length > 0 ? actions : m.actions,
                }
              : m,
          );
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
          const session = s.sessions[sessionId];
          return {
            messages: {
              ...s.messages,
              [sessionId]: list.map((m) =>
                m.id === assistantId ? { ...m, status: "canceled" as const } : m,
              ),
            },
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
      storage: localJsonStorage,
      // streamStatus es efímero: se omite de la persistencia (al rehidratar
      // toma su valor inicial "idle" de initialState), no se escribe a disco.
      partialize: (s) => ({ sessions: s.sessions, messages: s.messages }),
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
