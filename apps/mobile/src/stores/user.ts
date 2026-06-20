import { createUserStore } from "@ynara/core/stores";
import { secureStorage } from "@/lib/secureStorage";

// Instancia mobile del user store (ADR-016): la lógica vive en @ynara/core;
// acá se inyecta SecureStore como storage (regla #5: el JWT va a SecureStore).
export const useUserStore = createUserStore(secureStorage);

export type { UserProfile } from "@ynara/core/stores";
