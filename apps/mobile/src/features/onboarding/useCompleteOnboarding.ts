import { type Mode, ModeSchema } from "@ynara/shared-schemas";
import { useRouter } from "expo-router";
import { useCallback } from "react";
import { useOnboardingStore } from "@/stores/onboarding";
import { useOnboardingStepStore } from "@/stores/onboardingStep";
import { useUserStore } from "@/stores/user";

/**
 * Cierre del onboarding (mobile).
 *
 * Traslada el draft al user store (incluido el token que dejó el AuthStep) y
 * marca el onboarding como completo. El backend NO tiene `POST /v1/user/onboard`:
 * el flag `onboarding_completed` se maneja client-side, y nombre/mood/modos
 * quedan en el user store (no hay endpoint para persistirlos todavía).
 *
 * Es una operación síncrona (solo escribe stores + navega), así que no expone
 * estado de carga.
 */
export function useCompleteOnboarding() {
  const router = useRouter();

  const complete = useCallback(() => {
    const draft = useOnboardingStore.getState();
    const user = useUserStore.getState();

    // Cierre local (no hay endpoint de onboard): el token ya viene del AuthStep
    // en el draft y acá se commitea al user store, de donde lo lee el cliente API.
    user.setDisplayName(draft.displayName);
    user.setMood(draft.mood, draft.moodFreeText);
    // `interestedModes` es string[] en el draft; validamos contra el enum antes
    // de pasarlo al user store (descarta basura de un persist viejo o un modo
    // eliminado) en vez de un cast a ciegas.
    const interestedModes = draft.interestedModes.filter(
      (m): m is Mode => ModeSchema.safeParse(m).success,
    );
    user.setInterestedModes(interestedModes);
    if (draft.authedUserId && draft.authedToken) {
      user.setAuth({
        userId: draft.authedUserId,
        token: draft.authedToken,
        isEphemeral: draft.authMode === "ephemeral",
      });
    }
    user.completeOnboarding();
    useOnboardingStore.getState().reset();
    useOnboardingStepStore.getState().reset();

    router.replace("/");
  }, [router]);

  return { complete };
}
