import { View } from "react-native";

/**
 * Placeholder del timeline mientras carga `GET /v1/memory`: filas mudas que
 * espejan la altura de las cards de `TimelineEntryRow` (dot + 3 líneas) para
 * evitar el salto de layout al llegar los datos.
 */
export function MemoryTimelineSkeleton() {
  return (
    <View
      className="gap-3"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      {[0, 1, 2, 3, 4].map((i) => (
        <View
          key={i}
          className="flex-row items-start gap-3 rounded-lg border border-border bg-bg p-4"
        >
          <View className="mt-1 h-2 w-2 shrink-0 rounded-pill bg-bg-soft" />
          <View className="flex-1 gap-2">
            <View className="h-3 w-16 rounded-sm bg-bg-soft" />
            <View className="h-4 w-full rounded-sm bg-bg-soft" />
            <View className="h-4 w-2/3 rounded-sm bg-bg-soft" />
          </View>
        </View>
      ))}
    </View>
  );
}
