import { Text, View } from "react-native";
import { useUserStore } from "@/stores/user";

// Pantalla placeholder de la Fase 2: confirma que la infra está cableada
// (providers + user store de @ynara/core sobre SecureStore). El redirect real
// según sesión (onboarding vs hoy) se agrega cuando existan esas rutas.
export default function Index() {
  const onboardingCompleted = useUserStore((s) => s.onboardingCompleted);

  return (
    <View className="flex-1 items-center justify-center gap-4 p-8">
      <Text className="text-3xl font-semibold">Ynara</Text>
      <Text className="text-base text-center opacity-70">
        Asistente personal adaptativo con memoria propia.
      </Text>
      <Text className="text-xs text-center opacity-50">
        Infra lista. Onboarding completado: {onboardingCompleted ? "sí" : "no"}.
      </Text>
    </View>
  );
}
