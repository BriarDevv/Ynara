import { Text, View } from "react-native";

export default function Index() {
  return (
    <View className="flex-1 items-center justify-center gap-4 p-8">
      <Text className="text-3xl font-semibold">Ynara</Text>
      <Text className="text-base opacity-70 text-center">
        Asistente personal adaptativo con memoria propia.
      </Text>
      <Text className="text-xs opacity-50 text-center">
        Scaffold inicial — pendiente UI definitiva.
      </Text>
    </View>
  );
}
