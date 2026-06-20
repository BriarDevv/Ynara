import type { Mode } from "@ynara/shared-schemas";
import { Pressable, View } from "react-native";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { MODE_DESCRIPTORS, MODE_DOT_CLASS } from "@/components/ui/modes";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";
import { useUserStore } from "@/stores/user";

type Props = {
  open: boolean;
  current: Mode;
  onClose: () => void;
  onSelect: (mode: Mode) => void;
};

/**
 * Selector de modo del chat: al elegir, vas a la conversación de ese modo
 * (modelo "una sesión = un modo"). Marca el modo actual.
 */
export function ChatModeSheet({ open, current, onClose, onSelect }: Props) {
  const interestedModes = useUserStore((s) => s.interestedModes);
  const ordered = [...MODE_DESCRIPTORS].sort(
    (a, b) => Number(interestedModes.includes(b.id)) - Number(interestedModes.includes(a.id)),
  );

  return (
    <BottomSheet open={open} onClose={onClose}>
      <View className="gap-4 px-6 pb-6 pt-5">
        <View className="gap-1">
          <Text className="text-title font-display text-ink-deep">Cambiar de modo</Text>
          <Text className="text-body-sm text-ink-soft">
            Cada modo tiene su propia conversación.
          </Text>
        </View>

        <View className="gap-3">
          {ordered.map((m) => {
            const selected = m.id === current;
            return (
              <Pressable
                key={m.id}
                accessibilityRole="button"
                accessibilityState={{ selected }}
                onPress={() => onSelect(m.id)}
                className={cn(
                  "rounded-lg border p-4 active:bg-bg-soft",
                  selected ? "border-border-strong bg-bg-soft" : "border-border bg-bg",
                )}
              >
                <View className="flex-row items-center gap-3">
                  <View className={cn("h-3 w-3 rounded-pill", MODE_DOT_CLASS[m.id])} />
                  <View className="flex-1">
                    <Text className="text-body font-body-semibold text-ink">{m.label}</Text>
                    <Text className="text-body-sm text-ink-soft">{m.blurb}</Text>
                  </View>
                  {selected ? <Text className="text-body-sm text-ink-soft">Actual</Text> : null}
                </View>
              </Pressable>
            );
          })}
        </View>
      </View>
    </BottomSheet>
  );
}
