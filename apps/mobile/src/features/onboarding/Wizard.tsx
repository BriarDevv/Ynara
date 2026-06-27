import { useEffect } from "react";
import { BackHandler, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { LivingField } from "@/components/ui/LivingField";
import { OnboardingHeader } from "./components/OnboardingHeader";
import type { OnboardingStepId } from "./steps";
import { A11yStep } from "./steps/A11yStep";
import { AuthStep } from "./steps/AuthStep";
import { ModesStep } from "./steps/ModesStep";
import { MoodStep } from "./steps/MoodStep";
import { NameStep } from "./steps/NameStep";
import { SobreVosStep } from "./steps/SobreVosStep";
import { useOnboardingNav } from "./useOnboardingNav";

// Los 6 steps del onboarding. El switch es exhaustivo sobre `OnboardingStepId`
// (lista mobile, incluye "sobre-vos"); `null` por si la unión crece.
function renderStep(step: OnboardingStepId) {
  switch (step) {
    case "auth":
      return <AuthStep />;
    case "nombre":
      return <NameStep />;
    case "dia":
      return <MoodStep />;
    case "modos":
      return <ModesStep />;
    case "sobre-vos":
      return <SobreVosStep />;
    case "a11y":
      return <A11yStep />;
    default:
      return null;
  }
}

/**
 * Wizard del onboarding (mobile): una sola pantalla manejada por el step store
 * (mobile). Header con progreso fijo arriba + el step actual abajo.
 */
export function OnboardingWizard() {
  const { currentStep, index, total, isFirst, back } = useOnboardingNav();

  // Android: el botón "atrás" del sistema vuelve un paso en vez de salir del
  // onboarding; en el primer paso deja salir (return false). Espeja el back del
  // browser que el web ya tiene vía rutas. (iOS no tiene back de hardware.)
  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (!isFirst) {
        back();
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [isFirst, back]);

  return (
    <View className="flex-1 bg-bg-canvas">
      <LivingField variant="aurora" />
      <SafeAreaView className="flex-1" edges={["top", "bottom"]}>
        <OnboardingHeader total={total} current={index} />
        <View className="flex-1">{renderStep(currentStep)}</View>
      </SafeAreaView>
    </View>
  );
}
