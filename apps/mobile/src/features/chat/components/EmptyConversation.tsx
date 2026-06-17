import { MODE_INTRO } from "@ynara/core/features/chat";
import type { Mode } from "@ynara/shared-schemas";
import { View } from "react-native";
import { Text } from "@/components/ui/Text";

/**
 * Estado vacío de la conversación: la intro del modo (copy compartido de
 * @ynara/core, `MODE_INTRO`).
 */
export function EmptyConversation({ mode }: { mode: Mode }) {
  return (
    <View className="flex-1 items-center justify-center px-8">
      <Text className="text-body text-center text-ink-soft">{MODE_INTRO[mode]}</Text>
    </View>
  );
}
