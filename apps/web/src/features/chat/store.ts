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

      reset: () => set(initialState),
    }),
    {
      name: "ynara.chat",
      storage: localJsonStorage,
      // streamStatus es efímero: se omite de la persistencia (al rehidratar
      // toma su valor inicial "idle" de initialState), no se escribe a disco.
      partialize: (s) => ({ sessions: s.sessions, messages: s.messages }),
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
