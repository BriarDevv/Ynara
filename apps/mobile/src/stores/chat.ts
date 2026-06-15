import { createChatStore } from "@ynara/core/features/chat";
import { memoryStorage } from "@/lib/memoryStorage";

// Instancia mobile del chat store (ADR-012): la lógica vive en @ynara/core; acá
// se inyecta storage en memoria (el historial es efímero por ahora — AsyncStorage
// queda como follow-up). El token/perfil viven en el user store (SecureStore).
export const useChatStore = createChatStore(memoryStorage);
