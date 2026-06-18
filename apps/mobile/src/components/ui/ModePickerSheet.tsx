import { Modal, Pressable, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Text } from "@/components/ui/Text";
import { useActiveMode } from "@/hooks/useActiveMode";
import { cn } from "@/lib/cn";
import { useActiveModeStore } from "@/stores/mode";
import { useUserStore } from "@/stores/user";
import { MODE_DESCRIPTORS, MODE_DOT_CLASS } from "./modes";

type Props = {
  open: boolean;
  onClose: () => void;
};

/**
 * Selector de modo activo (F2): `Modal` bottom-anchored (patrón de RecapSheet —
 * RN no tiene el Sheet de web). Lista los 5 modos ordenados onboarding-primero
 * (igual que ChatHome), marca el activo y al elegir uno lo fija en el store
 * global y cierra. El tinte de la app (header/acentos) sigue al modo elegido.
 */
export function ModePickerSheet({ open, onClose }: Props) {
  const active = useActiveMode();
  const setMode = useActiveModeStore((s) => s.setMode);
  const interestedModes = useUserStore((s) => s.interestedModes);

  const ordered = [...MODE_DESCRIPTORS].sort(
    (a, b) => Number(interestedModes.includes(b.id)) - Number(interestedModes.includes(a.id)),
  );

  return (
    <Modal visible={open} animationType="slide" transparent onRequestClose={onClose}>
      <View className="flex-1 justify-end bg-black/40">
        <Pressable className="flex-1" accessibilityLabel="Cerrar" onPress={onClose} />

        <SafeAreaView edges={["bottom"]} className="rounded-t-xl bg-bg">
          <View className="gap-4 px-6 pb-6 pt-5">
            <View className="gap-1">
              <Text className="text-title font-display text-ink-deep">Modo</Text>
              <Text className="text-body-sm text-ink-soft">
                Elegí cómo querés que Ynara te acompañe.
              </Text>
            </View>

            <View className="gap-3">
              {ordered.map((m) => {
                const selected = m.id === active;
                return (
                  <Pressable
                    key={m.id}
                    accessibilityRole="button"
                    accessibilityState={{ selected }}
                    onPress={() => {
                      setMode(m.id);
                      onClose();
                    }}
                    className={cn(
                      "rounded-lg border p-4 active:bg-bg-soft",
                      selected ? "border-border-strong bg-bg-soft" : "border-border bg-bg",
                    )}
                  >
                    <View className="flex-row items-center gap-3">
                      <View className={cn("h-3 w-3 rounded-pill", MODE_DOT_CLASS[m.id])} />
                      <View className="flex-1">
                        <Text className="text-body font-semibold text-ink">{m.label}</Text>
                        <Text className="text-body-sm text-ink-soft">{m.blurb}</Text>
                      </View>
                      {selected ? <Text className="text-body-sm text-ink-soft">Activo</Text> : null}
                    </View>
                  </Pressable>
                );
              })}
            </View>
          </View>
        </SafeAreaView>
      </View>
    </Modal>
  );
}
