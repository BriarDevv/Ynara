import { View } from "react-native";
import { ProgressDots } from "@/components/ui/ProgressDots";
import { Text } from "@/components/ui/Text";

type Props = {
  total: number;
  current: number;
};

/**
 * Header del onboarding (mobile): wordmark + progreso. El "Saltar" con modal
 * de confirmación de la web se difiere (no es crítico para el flujo base).
 */
export function OnboardingHeader({ total, current }: Props) {
  return (
    <View className="flex-row items-center justify-between border-b border-border px-6 py-3.5">
      <Text className="text-body font-body-semibold text-ink-deep">Ynara</Text>
      <ProgressDots total={total} current={current} />
      {/* Spacer para centrar ópticamente el progreso (mismo ancho aprox que el wordmark). */}
      <View className="w-12" />
    </View>
  );
}
