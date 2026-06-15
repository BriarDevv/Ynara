import { useLocalSearchParams } from "expo-router";
import { ChatScreen } from "@/features/chat/ChatScreen";

// Ruta de la conversación (Expo Router): /chat/<sessionId>. El sessionId lo crea
// el selector de modo antes de navegar.
export default function ChatRoute() {
  const { sessionId } = useLocalSearchParams<{ sessionId: string }>();
  if (!sessionId) return null;
  return <ChatScreen sessionId={sessionId} />;
}
