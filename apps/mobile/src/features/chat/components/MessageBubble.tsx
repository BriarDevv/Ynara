import type { ChatUiMessage } from "@ynara/core/features/chat";
import type { Mode } from "@ynara/shared-schemas";
import { chatErrorCopy } from "@ynara/shared-schemas";
import { Pressable, Text, View } from "react-native";
import { MODE_DOT_CLASS } from "@/components/ui/modes";
import { cn } from "@/lib/cn";

type Props = {
  message: ChatUiMessage;
  mode: Mode;
  /** Reintentar el envío del mensaje del usuario que falló. */
  onRetry?: () => void;
};

/**
 * Una burbuja de la conversación (RN). Espejo del `MessageBubble` web:
 * - Usuario: derecha, fondo crema, texto plano.
 * - Assistant: izquierda, hairline con el tint del modo. (Markdown llega después;
 *   por ahora texto plano.)
 * - Error: burbuja de sistema con copy humano (mapeado de `errorCode`) + reintento.
 */
export function MessageBubble({ message, mode, onRetry }: Props) {
  if (message.status === "error") {
    return (
      <View className="items-start gap-2">
        <View className="max-w-[85%] rounded-md border border-error bg-error-soft px-4 py-3">
          <Text className="text-body text-ink">{chatErrorCopy(message.errorCode)}</Text>
        </View>
        {onRetry ? (
          <Pressable accessibilityRole="button" onPress={onRetry} className="px-3 py-1.5">
            <Text className="text-body-sm text-ink-soft underline">Reintentar</Text>
          </Pressable>
        ) : null}
      </View>
    );
  }

  if (message.role === "user") {
    return (
      <View className="items-end">
        <View
          className={cn(
            "max-w-[85%] rounded-md bg-bg-soft px-4 py-3",
            message.status === "sending" && "opacity-70",
          )}
        >
          <Text className="text-body text-ink">{message.text}</Text>
        </View>
      </View>
    );
  }

  // assistant
  return (
    <View className="flex-row justify-start">
      <View className="max-w-[85%] flex-row gap-3">
        <View className={cn("mt-1 w-0.5 self-stretch rounded-pill", MODE_DOT_CLASS[mode])} />
        <Text className="flex-1 text-body text-ink">{message.text}</Text>
      </View>
    </View>
  );
}
