import { Redirect } from "expo-router";
import { Text, View } from "react-native";
import { useUserStore } from "@/stores/user";

// Entrada de la app: si el onboarding no está completo, va al flujo de
// onboarding. (La pantalla "hoy" todavía no existe; cuando llegue, el usuario
// ya onboardeado redirige ahí.)
export default function Index() {
  const onboardingCompleted = useUserStore((s) => s.onboardingCompleted);

  if (!onboardingCompleted) {
    return <Redirect href="/onboarding" />;
  }

  return (
    <View className="flex-1 items-center justify-center gap-4 bg-bg-canvas p-8">
      <Text className="text-hero font-semibold text-ink">Ynara</Text>
      <Text className="text-body text-center text-ink-soft">
        Onboarding completo. La pantalla principal llega pronto.
      </Text>
    </View>
  );
}
