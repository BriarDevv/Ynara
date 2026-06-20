import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { ToolCallOutT } from "@/features/playground/schemas";
import { clientStorage } from "@/lib/clientStorage";

/**
 * Historial de sesiones del Playground (client-side, persistido en localStorage).
 *
 * El Playground es AISLADO por diseño (ADR-018: no persiste en backend, no toca
 * memoria ni sesiones del producto). Para que el operador no pierda sus pruebas
 * al navegar, las conversaciones de prueba viven acá, en el browser, separadas de
 * la sesión admin (`stores/admin.ts`). Cero PII del usuario final: son los
 * mensajes que el propio operador le manda al modelo.
 *
 * Persiste con la key `ynara.admin.playground`. Cada sesión es un hilo de turnos
 * (user/assistant); el assistant guarda además las métricas del turno (modelo,
 * tokens, latencia, tok/s, thinking) para reconstruir el inspector sin re-pegar.
 */

export type ChatRole = "user" | "assistant";

/** Un turno del hilo. El user solo lleva `content`; el assistant, las métricas. */
export type ChatTurn = {
  id: string;
  role: ChatRole;
  content: string;
  /** Estado del turno assistant: `ok` (generó) | `error` (falló el stream). */
  status: "ok" | "error";
  // --- metadata del turno assistant (ausente en user) ---
  model?: string;
  finishReason?: string;
  completionTokens?: number;
  latencyMs?: number;
  tokensPerSecond?: number;
  thinkingUsed?: boolean;
  /** El `<think>…</think>` separado (qwen), o `null`. */
  thinking?: string | null;
  /** `true` si el turno corrió en modo agente (tool-loop observado). */
  agent?: boolean;
  /** Tool-calls observadas del loop agente (qwen), si `agent===true`. */
  actions?: ToolCallOutT[];
  /** Status HTTP del error (para mapear copy neutro), si `status==="error"`. */
  errorStatus?: number | null;
  createdAt: number;
};

export type PlaygroundSession = {
  id: string;
  title: string;
  messages: ChatTurn[];
  createdAt: number;
  updatedAt: number;
};

type State = {
  sessions: PlaygroundSession[];
  activeId: string | null;
};

type Actions = {
  /** Crea una sesión vacía y la deja activa; devuelve su id. */
  newSession: () => string;
  selectSession: (id: string) => void;
  deleteSession: (id: string) => void;
  renameSession: (id: string, title: string) => void;
  /** Agrega un turno a una sesión (y autotitula con el 1er mensaje del operador). */
  appendMessage: (sessionId: string, message: ChatTurn) => void;
  /** Vacía los mensajes de la sesión activa (sin borrarla). */
  clearActive: () => void;
  /** Saca el último turno de una sesión (p. ej. el error antes de reintentar). */
  dropLast: (sessionId: string) => void;
};

const DEFAULT_TITLE = "Nueva sesión";
const TITLE_MAX = 42;

/** Título derivado del primer mensaje del operador (truncado, una línea). */
function deriveTitle(content: string): string {
  const oneLine = content.replace(/\s+/g, " ").trim();
  if (oneLine.length === 0) return DEFAULT_TITLE;
  return oneLine.length > TITLE_MAX ? `${oneLine.slice(0, TITLE_MAX)}…` : oneLine;
}

export const usePlaygroundSessions = create<State & Actions>()(
  persist(
    (set, get) => ({
      sessions: [],
      activeId: null,

      newSession: () => {
        const id = crypto.randomUUID();
        const now = Date.now();
        const session: PlaygroundSession = {
          id,
          title: DEFAULT_TITLE,
          messages: [],
          createdAt: now,
          updatedAt: now,
        };
        set((state) => ({ sessions: [session, ...state.sessions], activeId: id }));
        return id;
      },

      selectSession: (id) => set({ activeId: id }),

      deleteSession: (id) =>
        set((state) => {
          const sessions = state.sessions.filter((s) => s.id !== id);
          const activeId = state.activeId === id ? (sessions[0]?.id ?? null) : state.activeId;
          return { sessions, activeId };
        }),

      renameSession: (id, title) =>
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === id ? { ...s, title: title.trim() || DEFAULT_TITLE } : s,
          ),
        })),

      appendMessage: (sessionId, message) =>
        set((state) => ({
          sessions: state.sessions.map((s) => {
            if (s.id !== sessionId) return s;
            const isFirstUser =
              message.role === "user" &&
              s.title === DEFAULT_TITLE &&
              !s.messages.some((m) => m.role === "user");
            return {
              ...s,
              title: isFirstUser ? deriveTitle(message.content) : s.title,
              messages: [...s.messages, message],
              updatedAt: Date.now(),
            };
          }),
        })),

      clearActive: () =>
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === get().activeId ? { ...s, messages: [], updatedAt: Date.now() } : s,
          ),
        })),

      dropLast: (sessionId) =>
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === sessionId ? { ...s, messages: s.messages.slice(0, -1) } : s,
          ),
        })),
    }),
    { name: "ynara.admin.playground", storage: createJSONStorage(() => clientStorage) },
  ),
);
