import type { OnboardingStep } from "@ynara/core/features/onboarding";
import { View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { OnboardingHeader } from "./components/OnboardingHeader";
import { A11yStep } from "./steps/A11yStep";
import { AuthStep } from "./steps/AuthStep";
import { ModesStep } from "./steps/ModesStep";
import { MoodStep } from "./steps/MoodStep";
import { NameStep } from "./steps/NameStep";
import { useOnboardingNav } from "./useOnboardingNav";

// Los 5 steps del onboarding, ya todos implementados. El switch es exhaustivo
// sobre `OnboardingStep`; `null` solo por si la unión crece sin actualizar acá.
function renderStep(step: OnboardingStep) {
  switch (step) {
    case "auth":
      return <AuthStep />;
    case "nombre":
      return <NameStep />;
    case "dia":
      return <MoodStep />;
    case "modos":
      return <ModesStep />;
    case "a11y":
      return <A11yStep />;
    default:
      return null;
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
