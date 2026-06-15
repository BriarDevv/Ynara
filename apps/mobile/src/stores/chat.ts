import { createChatStore } from "@ynara/core/features/chat";
import { asyncStorage } from "@/lib/asyncStorage";

// Instancia mobile del chat store (ADR-012): la lógica vive en @ynara/core; acá
// se inyecta AsyncStorage (el historial NO es secreto y persiste entre recargas;
// el token/perfil van en el user store sobre SecureStore, regla #5).
export const useChatStore = createChatStore(asyncStorage);
