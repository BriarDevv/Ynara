import { View } from "react-native";

/**
 * Placeholder de las sugerencias mientras carga `GET /v1/suggestions`: dos filas
 * mudas que espejan la altura de `SuggestionCard` (barra de acento + dos líneas).
 */
export function SuggestionsSkeleton() {
  return (
    <View
      className="gap-3"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      {[0, 1].map((i) => (
        <View key={i} className="flex-row items-stretch gap-3 py-3.5">
          <View className="w-1 shrink-0 rounded-pill bg-bg-soft" />
          <View className="flex-1 gap-2">
            <View className="h-4 w-1/2 rounded-sm bg-bg-soft" />
            <View className="h-3 w-3/4 rounded-sm bg-bg-soft" />
          </View>
        </View>
      ))}
    </View>
  );
}
