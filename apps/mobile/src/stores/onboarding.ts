import { createOnboardingStore } from "@ynara/core/features/onboarding";
import { memoryStorage } from "@/lib/memoryStorage";

// Instancia mobile del draft store de onboarding (ADR-012): la lógica vive en
// @ynara/core; acá se inyecta storage en memoria (el draft es de una sola
// sesión; ver memoryStorage).
export const useOnboardingStore = createOnboardingStore(memoryStorage);
