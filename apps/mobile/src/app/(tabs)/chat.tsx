import { ChatTab } from "@/features/chat/ChatTab";

// Tab "Chat": entrás directo a una conversación (sin home intermedia). El modo y
// los recientes se manejan dentro del tab (in-place).
export default function ChatTabRoute() {
  return <ChatTab />;
}
