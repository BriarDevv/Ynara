import { KeyboardAvoidingView, Platform, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useChatStore } from "@/stores/chat";
import { ChatComposer } from "./components/ChatComposer";
import { ChatHeader } from "./components/ChatHeader";
import { MessageList } from "./components/MessageList";
import { useChatStream } from "./useChatStream";

/**
 * Pantalla de conversación (M2, streaming). Flujo optimistic: el mensaje del
 * usuario aparece al instante y `useChatStream` abre el stream (token a token);
 * el placeholder del assistant crece con cada delta y se cierra en "done".
 * Mientras streamea, el composer queda en modo "Detener" (cancela).
 * `KeyboardAvoidingView` para que el teclado no tape el composer.
 */
export function ChatScreen({ sessionId }: { sessionId: string }) {
  const session = useChatStore((s) => s.sessions[sessionId]);
  const messages = useChatStore((s) => s.messages[sessionId]);
  const appendUserMessage = useChatStore((s) => s.appendUserMessage);
  const setMessageStatus = useChatStore((s) => s.setMessageStatus);
  const stream = useChatStream(sessionId);

  if (!session) return null;
  const mode = session.mode;

  const handleSend = (text: string) => {
    const userMessageId = appendUserMessage(sessionId, text);
    stream.send({ text, mode, session_id: sessionId }, userMessageId);
  };

  const handleRetry = (messageId: string, text: string) => {
    setMessageStatus(sessionId, messageId, "sending");
    stream.send({ text, mode, session_id: sessionId }, messageId);
  };

  return (
    <SafeAreaView className="flex-1 bg-bg-canvas" edges={["top", "bottom"]}>
      <ChatHeader mode={mode} />
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
    </SafeAreaView>
  );
}
