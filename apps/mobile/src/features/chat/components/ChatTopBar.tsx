import type { Mode } from "@ynara/shared-schemas";
import { Pressable, View } from "react-native";
import { MODE_BY_ID, MODE_DOT_CLASS } from "@/components/ui/modes";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";

type Props = {
  mode: Mode;
  onPressMode: () => void;
  onPressRecents: () => void;
};

/**
 * Barra superior del chat: chip de modo (izq, abre el selector) + ícono de
 * recientes (der, abre el panel de conversaciones).
 */
export function ChatTopBar({ mode, onPressMode, onPressRecents }: Props) {
  return (
    <View className="flex-row items-center justify-between border-b border-border px-4 py-3">
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Modo ${MODE_BY_ID[mode].label}. Tocá para cambiar.`}
        onPress={onPressMode}
        hitSlop={8}
        className="flex-row items-center gap-2 rounded-pill border border-border bg-bg px-3 py-1.5 active:bg-bg-soft"
      >
        <View className={cn("h-2.5 w-2.5 rounded-pill", MODE_DOT_CLASS[mode])} />
        <Text className="text-body-sm font-body-semibold text-ink">{MODE_BY_ID[mode].label}</Text>
        <Text className="text-caption text-ink-soft">▾</Text>
      </Pressable>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Conversaciones recientes"
        onPress={onPressRecents}
        hitSlop={12}
        className="items-center justify-center gap-1 rounded-lg border border-border bg-bg px-3 py-2 active:bg-bg-soft"
      >
        {/* Hamburguesa clásico dentro de un recuadro (como el chip de modo): el
            fondo `bg` opaco lo despega del fondo animado y las 3 líneas se ven
            nítidas. */}
        <View className="h-0.5 w-5 rounded-pill bg-ink" />
        <View className="h-0.5 w-5 rounded-pill bg-ink" />
        <View className="h-0.5 w-5 rounded-pill bg-ink" />
      </Pressable>
    </View>
  );
}
