import type { Recap } from "@ynara/shared-schemas";
import { Modal, Pressable, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Text } from "@/components/ui/Text";
import { formatHoyDate } from "../format";

type Props = {
  open: boolean;
  onClose: () => void;
  recap: Recap;
};

/**
 * Sheet del recap del día (wireframe 15): el borrador que Ynara armó — un
 * headline editorial + los highlights. RN no tiene el `Sheet` de web, así que es
 * un `Modal` bottom-anchored (backdrop tappable para cerrar + panel redondeado
 * arriba). Cerrar el día de verdad (regenerar con el LLM) es fase de backend.
 */
export function RecapSheet({ open, onClose, recap }: Props) {
  return (
    <Modal visible={open} animationType="slide" transparent onRequestClose={onClose}>
      <View className="flex-1 justify-end bg-black/40">
        {/* Backdrop: tap fuera del panel cierra. */}
        <Pressable className="flex-1" accessibilityLabel="Cerrar" onPress={onClose} />

        <SafeAreaView edges={["bottom"]} className="rounded-t-xl bg-bg">
          <View className="gap-5 px-6 pb-6 pt-5">
            <View className="gap-1">
              <Text className="text-title font-display text-ink-deep">Recap del día</Text>
              <Text className="text-body-sm text-ink-soft">
                {formatHoyDate(new Date(recap.date))}
              </Text>
            </View>

            {recap.headline ? (
              <Text className="text-body font-body-medium text-ink">{recap.headline}</Text>
            ) : null}

            {recap.highlights.length > 0 ? (
              <View className="gap-3">
                {recap.highlights.map((highlight) => (
                  <View key={highlight} className="flex-row items-start gap-3">
                    <View className="mt-2 h-1.5 w-1.5 shrink-0 rounded-pill bg-ink-faint" />
                    <Text className="flex-1 text-body text-ink-soft">{highlight}</Text>
                  </View>
                ))}
              </View>
            ) : (
              <Text className="text-body text-ink-soft">
                Todavía no hay nada para repasar. A medida que pase el día, esto se llena.
              </Text>
            )}

            <Pressable
              accessibilityRole="button"
              onPress={onClose}
              className="self-start rounded-pill bg-bg-soft px-5 py-2.5 active:bg-border"
            >
              <Text className="text-button text-ink">Listo</Text>
            </Pressable>
          </View>
        </SafeAreaView>
      </View>
    </Modal>
  );
}
