import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { clientStorage } from "@/lib/clientStorage";

/**
 * Mapeo web-local `localSessionId → backendSessionId` (reconcile onboarding→chat).
 *
 * El store de chat (packages/core) genera un UUID en el cliente
 * (`crypto.randomUUID`) para rutear la URL `/chat/[id]` y agrupar mensajes. Ese
 * id NUNCA existe server-side: el backend solo crea una `ChatSession` cuando el
 * request manda `session_id: null`, y devuelve 404 para cualquier id que no
 * insertó él (`_sessions.py:resolve_chat_session`). Por eso:
 *
 *  1. El PRIMER turno de una sesión manda `session_id: null` → el backend crea
 *     la sesión y devuelve su id real en el evento `done` del stream.
 *  2. La web adopta ese id acá (`setBackendSessionId`) y lo reusa en los turnos
 *     siguientes (`getBackendSessionId`), encadenando la conversación.
 *
 * Vive en `apps/web` (NO en packages/core) para mantener el fix 100% web-local:
 * no extiende el schema del store compartido. Se persiste en localStorage para
 * que el mapeo sobreviva un refresh y los turnos sigan encadenando.
 *
 * El id local sigue siendo la fuente de verdad para la URL y el store de chat;
 * este mapeo es solo "qué `session_id` mando al backend".
 */

type BackendSessionState = {
  /** localSessionId → backendSessionId (id real confirmado por el backend). */
  byLocalId: Record<string, string>;
};

type BackendSessionActions = {
  /** Adopta el id real que el backend devolvió en `done` para una sesión local. */
  setBackendSessionId: (localSessionId: string, backendSessionId: string) => void;
  /** id real del backend para una sesión local, o null si aún no se confirmó. */
  getBackendSessionId: (localSessionId: string) => string | null;
  reset: () => void;
};

const initialState: BackendSessionState = { byLocalId: {} };

export const useBackendSessionStore = create<BackendSessionState & BackendSessionActions>()(
  persist(
    (set, get) => ({
      ...initialState,

      setBackendSessionId: (localSessionId, backendSessionId) =>
        set((s) => {
          // Idempotente: si ya está mapeado al mismo id, no re-render.
          if (s.byLocalId[localSessionId] === backendSessionId) return s;
          return { byLocalId: { ...s.byLocalId, [localSessionId]: backendSessionId } };
        }),

      getBackendSessionId: (localSessionId) => get().byLocalId[localSessionId] ?? null,

      reset: () => set(initialState),
    }),
    {
      name: "ynara.chat.backendSessions",
      storage: createJSONStorage(() => clientStorage),
    },
  ),
);
