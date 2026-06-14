import type { OnboardingStep } from "@ynara/core/features/onboarding";
import { View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { OnboardingHeader } from "./components/OnboardingHeader";
import { MoodStep } from "./steps/MoodStep";
import { NameStep } from "./steps/NameStep";
import { PlaceholderStep } from "./steps/PlaceholderStep";
import { useOnboardingNav } from "./useOnboardingNav";

// Steps implementados; el resto cae al PlaceholderStep (navegable) hasta que
// cada uno llegue en su propio PR.
function renderStep(step: OnboardingStep) {
  switch (step) {
    case "nombre":
      return <NameStep />;
    case "dia":
      return <MoodStep />;
    default:
      return <PlaceholderStep step={step} />;
  }
}

/**
 * Wizard del onboarding (mobile): una sola pantalla manejada por `currentStep`
 * del draft store. Header con progreso fijo arriba + el step actual abajo.
 */
export function OnboardingWizard() {
  const { currentStep, index, total } = useOnboardingNav();

  return (
    <SafeAreaView className="flex-1 bg-bg-canvas" edges={["top", "bottom"]}>
      <OnboardingHeader total={total} current={index} />
      <View className="flex-1">{renderStep(currentStep)}</View>
    </SafeAreaView>
  );
}
