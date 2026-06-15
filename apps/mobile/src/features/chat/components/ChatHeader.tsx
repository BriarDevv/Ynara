import type { Mode } from "@ynara/shared-schemas";
import { useRouter } from "expo-router";
import { Pressable, Text, View } from "react-native";
import { ModeChip } from "@/components/ui/ModeChip";

/**
 * Header de la conversación: volver al selector de modo (cambiar de modo =
 * sesión nueva, plan §4.4) + el `ModeChip` del modo de esta sesión.
 */
export function ChatHeader({ mode }: { mode: Mode }) {
  const router = useRouter();
  return (
    <View className="flex-row items-center justify-between border-b border-border px-4 py-3">
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Volver a los modos"
        onPress={() => router.back()}
        hitSlop={8}
      >
        <Text className="text-body text-ink-soft">‹ Modos</Text>
      </Pressable>
      <ModeChip mode={mode} />
    </View>
  );
}
