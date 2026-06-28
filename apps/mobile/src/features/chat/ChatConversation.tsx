import { KeyboardAvoidingView, Platform, View } from "react-native";
import { useBackendSessionStore } from "@/stores/backendSessions";
import { useChatStore } from "@/stores/chat";
import { ChatComposer } from "./components/ChatComposer";
import { MessageList } from "./components/MessageList";
import { useChatStream } from "./useChatStream";

/**
 * Área de conversación (mensajes + composer + streaming) de una sesión. El shell
 * (fondo, SafeAreaView, barra superior) lo pone `ChatTab`. Se monta con
 * `key={sessionId}` por sesión, así el stream se reinicia limpio al cambiar.
 */
export function ChatConversation({ sessionId }: { sessionId: string }) {
  const session = useChatStore((s) => s.sessions[sessionId]);
  const messages = useChatStore((s) => s.messages[sessionId]);
  const appendUserMessage = useChatStore((s) => s.appendUserMessage);
  const setMessageStatus = useChatStore((s) => s.setMessageStatus);
  const getBackendSessionId = useBackendSessionStore((s) => s.getBackendSessionId);
  const stream = useChatStream(sessionId);

  if (!session) return null;
  const mode = session.mode;

  // session_id que mandamos al backend: el id REAL ya confirmado para esta sesión
  // local, o null en el 1er turno (el backend crea la ChatSession y devuelve su id
  // en `done`, que el stream adopta). Mandar el id local hacía 404ear el turno.
  const handleSend = (text: string) => {
    const userMessageId = appendUserMessage(sessionId, text);
    stream.send({ text, mode, session_id: getBackendSessionId(sessionId) }, userMessageId);
  };

  const handleRetry = (messageId: string, text: string) => {
    setMessageStatus(sessionId, messageId, "sending");
    stream.send({ text, mode, session_id: getBackendSessionId(sessionId) }, messageId);
  };

  return (
    <KeyboardAvoidingView
      className="flex-1"
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View className="flex-1">
        <MessageList messages={messages ?? []} mode={mode} onRetry={handleRetry} />
      </View>
      <View className="px-4 pb-2">
        <ChatComposer onSend={handleSend} busy={stream.isStreaming} onCancel={stream.cancel} />
      </View>
    </KeyboardAvoidingView>
  );
}
