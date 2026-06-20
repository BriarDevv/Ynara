import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { asyncStorage } from "@/lib/asyncStorage";

/**
 * Estado mobile-only de la sesión de chat activa + cuándo se dejó el chat (para
 * el timeout de reanudación). Separado del chat store de core (que tiene las
 * sesiones/mensajes) para no tocar `packages/core`.
 */
type ChatSessionState = {
  activeSessionId: string | null;
  lastActiveAt: number | null;
};

type ChatSessionActions = {
  setActive: (id: string) => void;
  /** Marca cuándo dejaste el chat (Date.now()), para decidir reanudar al volver. */
  markLeft: () => void;
  reset: () => void;
};

export const useChatSessionStore = create<ChatSessionState & ChatSessionActions>()(
  persist(
    (set) => ({
      activeSessionId: null,
      lastActiveAt: null,
      setActive: (id) => set({ activeSessionId: id }),
      markLeft: () => set({ lastActiveAt: Date.now() }),
      reset: () => set({ activeSessionId: null, lastActiveAt: null }),
    }),
    { name: "ynara.chatSession", storage: createJSONStorage(() => asyncStorage) },
  ),
);
