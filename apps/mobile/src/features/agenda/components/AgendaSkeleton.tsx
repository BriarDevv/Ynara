import { View } from "react-native";

/**
 * Placeholder de la agenda mientras carga `GET /v1/events`: filas mudas que
 * espejan la altura de un evento para evitar el salto de layout. Mismo patrón
 * que `PrioritiesSkeleton` (Hoy).
 */
export function AgendaSkeleton() {
  return (
    <View
      className="gap-3"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      {[0, 1, 2, 3].map((i) => (
        <View key={i} className="flex-row gap-3 rounded-lg border border-border bg-bg p-4">
          <View className="w-1 self-stretch rounded-full bg-bg-soft" />
          <View className="flex-1 gap-2">
            <View className="h-3 w-1/4 rounded-sm bg-bg-soft" />
            <View className="h-4 w-3/5 rounded-sm bg-bg-soft" />
          </View>
        </View>
      ))}
    </View>
  );
}
