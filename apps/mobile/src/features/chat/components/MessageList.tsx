import type { ChatUiMessage } from "@ynara/core/features/chat";
import type { Mode } from "@ynara/shared-schemas";
import { useRef } from "react";
import { FlatList } from "react-native";
import { EmptyConversation } from "./EmptyConversation";
import { MessageBubble } from "./MessageBubble";

type Props = {
  messages: ChatUiMessage[];
  mode: Mode;
  onRetry: (messageId: string, text: string) => void;
};

/**
 * Lista de mensajes (FlatList). Auto-scroll al fondo cuando crece el contenido
 * (mensaje nuevo / respuesta). Estado vacío → intro del modo.
 */
export function MessageList({ messages, mode, onRetry }: Props) {
  const ref = useRef<FlatList<ChatUiMessage>>(null);

  if (messages.length === 0) {
    return <EmptyConversation mode={mode} />;
  }

  return (
    <FlatList
      ref={ref}
      data={messages}
      keyExtractor={(m) => m.id}
      renderItem={({ item }) => (
        <MessageBubble
          message={item}
          mode={mode}
          onRetry={
            item.role === "user" && item.status === "error"
              ? () => onRetry(item.id, item.text)
              : undefined
          }
        />
      )}
      contentContainerClassName="gap-4 px-4 py-4"
      onContentSizeChange={() => ref.current?.scrollToEnd({ animated: true })}
      keyboardShouldPersistTaps="handled"
    />
  );
}
