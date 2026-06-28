import { createBackendSessionStore } from "@ynara/core/features/chat";
import { asyncStorage } from "@/lib/asyncStorage";

/**
 * Instancia mobile del store de mapeo `localSessionId → backendSessionId`
 * (ADR-016): la lógica vive en `@ynara/core`; acá se inyecta AsyncStorage (el
 * mapeo no es secreto y persiste entre recargas para encadenar los turnos). El
 * porqué del mapeo (el backend 404ea ids de sesión que no creó él) está
 * documentado en el factory de core.
 */
export const useBackendSessionStore = createBackendSessionStore(asyncStorage);
