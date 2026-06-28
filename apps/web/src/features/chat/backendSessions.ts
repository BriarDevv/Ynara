import { createBackendSessionStore } from "@ynara/core/features/chat";
import { clientStorage } from "@/lib/clientStorage";

/**
 * Instancia web del store de mapeo `localSessionId → backendSessionId` (ADR-016):
 * la lógica vive en `@ynara/core`; acá se inyecta el storage sobre localStorage
 * (`clientStorage`) para que el mapeo sobreviva un refresh. El porqué del mapeo
 * (el backend 404ea ids de sesión que no creó él) está documentado en el factory
 * de core.
 */
export const useBackendSessionStore = createBackendSessionStore(clientStorage);
