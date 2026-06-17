import type { Mode } from "@ynara/shared-schemas";
import { View } from "react-native";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";
import { MODE_BY_ID, MODE_DOT_CLASS } from "./modes";

type Props = {
  mode: Mode;
  /** Override del label canónico del modo. */
  label?: string;
  className?: string;
};

/**
 * Chip de modo (RN): dot de color del modo + label. Espejo del `ModeChip` web.
 * El dot usa la clase estática de `MODE_DOT_CLASS` (NativeWind necesita el
 * className literal, no `bg-mode-${id}` dinámico).
 */
export function ModeChip({ mode, label, className }: Props) {
  return (
    <View
      className={cn(
        "flex-row items-center gap-2 self-start rounded-pill border border-border bg-bg px-3 py-1",
        className,
      )}
    >
      <View className={cn("h-2 w-2 rounded-pill", MODE_DOT_CLASS[mode])} />
      <Text className="text-body-sm text-ink">{label ?? MODE_BY_ID[mode].label}</Text>
    </View>
  );
}
