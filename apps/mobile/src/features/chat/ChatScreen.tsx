import type { Mode } from "@ynara/shared-schemas";
import { KeyboardAvoidingView, Platform, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useChatStore } from "@/stores/chat";
import { ChatComposer } from "./components/ChatComposer";
import { ChatHeader } from "./components/ChatHeader";
import { MessageList } from "./components/MessageList";
import { useSendChat } from "./useSendChat";

/**
 * Pantalla de conversación (M1, no-streaming). Orquesta header + lista +
 * composer sobre el chat store; el envío (optimistic + respuesta/error) lo
 * maneja `useSendChat`. `KeyboardAvoidingView` para que el teclado no tape el
 * composer.
 */
export function ChatScreen({ sessionId }: { sessionId: string }) {
  const session = useChatStore((s) => s.sessions[sessionId]);
  const messages = useChatStore((s) => s.messages[sessionId]);

  // La sesión se crea en el selector ANTES de navegar, así que acá siempre
  // existe; el fallback de modo es solo para satisfacer el hook si el store se
  // rehidrató sin la sesión (se corta abajo con el guard).
  const mode: Mode = session?.mode ?? "vida";
  const { send, retry, busy } = useSendChat(sessionId, mode);

  if (!session) return null;

  return (
    <SafeAreaView className="flex-1 bg-bg-canvas" edges={["top", "bottom"]}>
      <ChatHeader mode={session.mode} />
      <KeyboardAvoidingView
        className="flex-1"
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <View className="flex-1">
          <MessageList messages={messages ?? []} mode={session.mode} onRetry={retry} />
        </View>
        <View className="px-4 pb-2">
          <ChatComposer onSend={send} busy={busy} />
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
