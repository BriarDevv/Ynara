import { OnboardingWizard } from "@/features/onboarding/Wizard";

// Ruta del onboarding (expo-router). El wizard maneja los steps internamente
// vía el draft store; no hay rutas por step.
export default function OnboardingRoute() {
  return <OnboardingWizard />;
}
