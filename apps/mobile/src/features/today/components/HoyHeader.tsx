import type { Mode } from "@ynara/shared-schemas";
import { Pressable, View } from "react-native";
import { ModeChip } from "@/components/ui/ModeChip";
import { MODE_BY_ID } from "@/components/ui/modes";
import { Text } from "@/components/ui/Text";
import { formatHoyDate } from "../format";

type Props = {
  displayName: string;
  activeMode: Mode;
  /** Abre el selector de modo (F2). */
  onPressMode: () => void;
  /** Referencia temporal (inyectada para evitar drift entre renders). */
  now: Date;
};

/**
 * Header del dashboard Hoy (wireframe 06): fila superior con el chip de modo y
 * el avatar con la inicial, después el título "Hoy" + la fecha larga en español.
 * Espejo del `HoyHeader` de web.
 */
export function HoyHeader({ displayName, activeMode, onPressMode, now }: Props) {
  const initial = displayName.trim().charAt(0).toUpperCase();
  return (
    <View className="gap-4">
      <View className="flex-row items-center justify-between gap-3">
        <Pressable
          accessibilityRole="button"
          accessibilityHint="Cambiar modo"
          onPress={onPressMode}
          className="active:opacity-80"
        >
          <ModeChip mode={activeMode} label={`Modo: ${MODE_BY_ID[activeMode].label}`} />
        </Pressable>
        <View
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
          className="h-10 w-10 items-center justify-center rounded-pill bg-bg-soft"
        >
          <Text className="text-body-sm font-body-medium text-ink-soft">{initial || "?"}</Text>
        </View>
      </View>
      <View className="gap-1">
        <Text className="text-title font-display text-ink-deep">Hoy</Text>
        <Text className="text-body text-ink-soft">{formatHoyDate(now)}</Text>
      </View>
    </View>
  );
}
