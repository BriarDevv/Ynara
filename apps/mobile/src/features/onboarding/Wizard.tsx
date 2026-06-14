import { View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { OnboardingHeader } from "./components/OnboardingHeader";
import { NameStep } from "./steps/NameStep";
import { PlaceholderStep } from "./steps/PlaceholderStep";
import { useOnboardingNav } from "./useOnboardingNav";

/**
 * Wizard del onboarding (mobile): una sola pantalla manejada por `currentStep`
 * del draft store. Header con progreso fijo arriba + el step actual abajo.
 *
 * Por ahora solo el step de Nombre es real; el resto son placeholders que
 * mantienen el flujo navegable. Cada step real llega en su propio PR.
 */
export function OnboardingWizard() {
  const { currentStep, index, total } = useOnboardingNav();

  return (
    <SafeAreaView className="flex-1 bg-bg-canvas" edges={["top", "bottom"]}>
      <OnboardingHeader total={total} current={index} />
      <View className="flex-1">
        {currentStep === "nombre" ? <NameStep /> : <PlaceholderStep step={currentStep} />}
      </View>
    </SafeAreaView>
  );
}
