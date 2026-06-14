import { createChatStore } from "@ynara/core/features/chat";
import { clientStorage } from "@/lib/clientStorage";

// Instancia web del store de chat (ADR-012): la lógica vive en @ynara/core; acá
// se inyecta el storage SSR-safe sobre localStorage. Se mantiene el import
// `@/features/chat/store` (y los `../store` relativos) como superficie estable.
export const useChatStore = createChatStore(clientStorage);

export type {
  ChatMessageStatus,
  ChatSessionMeta,
  ChatStreamStatus,
  ChatUiMessage,
} from "@ynara/core/features/chat";
