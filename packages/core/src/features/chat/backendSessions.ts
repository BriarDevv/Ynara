import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

/**
 * Mapeo `localSessionId → backendSessionId` (reconcile cliente→chat), compartido
 * web + mobile (ADR-016). El storage del `persist` se inyecta: web pasa uno sobre
 * localStorage, mobile uno sobre AsyncStorage.
 *
 * El store de chat (core) genera un UUID en el cliente para rutear/agrupar
 * mensajes. Ese id NUNCA existe server-side: el backend solo crea una `ChatSession`
 * cuando el request manda `session_id: null`, y devuelve 404 para cualquier id que
 * no insertó él (`_sessions.py:resolve_chat_session`). Por eso:
 *
 *  1. El PRIMER turno de una sesión manda `session_id: null` → el backend crea la
 *     sesión y devuelve su id real en el evento `done` del stream.
 *  2. El cliente adopta ese id (`setBackendSessionId`) y lo reusa en los turnos
 *     siguientes (`getBackendSessionId`), encadenando la conversación. Sin esto el
 *     2do turno volvería a crear sesión (memoria/historial fragmentados); en mobile
 *     —que mandaba el id local— el backend 404eaba el turno entero.
 *
 * El id local sigue siendo la fuente de verdad para la URL/el store de chat; este
 * mapeo es solo "qué `session_id` mando al backend".
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

/**
 * Crea el store de mapeo sobre el `storage` provisto. Cada app lo instancia una
 * vez con el storage de su plataforma (misma clave de persist; los namespaces
 * quedan separados por backend de storage).
 */
export function createBackendSessionStore(storage: StateStorage) {
  return create<BackendSessionState & BackendSessionActions>()(
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
      { name: "ynara.chat.backendSessions", storage: createJSONStorage(() => storage) },
    ),
  );
}
