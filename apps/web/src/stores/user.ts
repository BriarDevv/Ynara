import { createUserStore } from "@ynara/core/stores";
import { clientStorage } from "@/lib/clientStorage";

// Instancia web del store de usuario (ADR-012): la lógica vive en @ynara/core;
// acá se inyecta el storage SSR-safe sobre localStorage. Se mantiene el import
// `@/stores/user` estable para los call-sites existentes.
export const useUserStore = createUserStore(clientStorage);

export type { UserProfile } from "@ynara/core/stores";
