import { ChatHome } from "@/features/chat/ChatHome";

// Tab "Chat" (ruta `/chat`): home de conversaciones. Abrir una empuja
// /chat/[sessionId] en el stack raíz (full-screen sobre el tab bar).
export default function ChatTab() {
  return <ChatHome />;
}
