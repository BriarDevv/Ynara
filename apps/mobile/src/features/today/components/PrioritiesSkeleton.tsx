import { View } from "react-native";

/**
 * Placeholder de las prioridades mientras carga `GET /v1/tasks`: tres filas
 * mudas que espejan la altura de `PriorityRow` para evitar el salto de layout al
 * llegar los datos. (El pulso animado de web queda pendiente: en RN iría con
 * Animated/Reanimated — el mock resuelve casi instantáneo, así que apenas se ve.)
 */
export function PrioritiesSkeleton() {
  return (
    <View
      className="gap-3"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      {[0, 1, 2].map((i) => (
        <View
          key={i}
          className="flex-row items-start gap-3 rounded-lg border border-border bg-bg p-4"
        >
          <View className="mt-0.5 h-6 w-6 rounded-pill bg-bg-soft" />
          <View className="flex-1 gap-2">
            <View className="h-4 w-3/5 rounded-sm bg-bg-soft" />
            <View className="h-3 w-2/5 rounded-sm bg-bg-soft" />
          </View>
        </View>
      ))}
    </View>
  );
}
