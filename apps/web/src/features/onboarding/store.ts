import { createOnboardingStore } from "@ynara/core/features/onboarding";
import { sessionClientStorage } from "@/lib/clientStorage";

// Instancia web del store del draft de onboarding (ADR-012): la lógica vive en
// @ynara/core; acá se inyecta el storage efímero sobre sessionStorage. Se
// mantiene el import `../store` de los steps/hooks como superficie estable.
export const useOnboardingStore = createOnboardingStore(sessionClientStorage);

export type { OnboardingDraft } from "@ynara/core/features/onboarding";
