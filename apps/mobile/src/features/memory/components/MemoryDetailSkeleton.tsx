import { View } from "react-native";

/**
 * Placeholder del detalle mientras carga `GET /v1/memory/{layer}/{ref}`: badge
 * de capa + el quote en dos líneas + dos celdas de meta, mudo.
 */
export function MemoryDetailSkeleton() {
  return (
    <View
      className="gap-7"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <View className="h-7 w-24 rounded-pill bg-bg-soft" />
      <View className="gap-3">
        <View className="h-6 w-full rounded-sm bg-bg-soft" />
        <View className="h-6 w-4/5 rounded-sm bg-bg-soft" />
      </View>
      <View className="flex-row gap-4">
        <View className="h-10 flex-1 rounded-md bg-bg-soft" />
        <View className="h-10 flex-1 rounded-md bg-bg-soft" />
      </View>
    </View>
  );
}
