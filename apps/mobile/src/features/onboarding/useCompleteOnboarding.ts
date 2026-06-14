import type { Mode } from "@ynara/shared-schemas";
import { useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { useOnboardingStore } from "@/stores/onboarding";
import { useUserStore } from "@/stores/user";

/**
 * Cierre del onboarding (mobile).
 *
 * Traslada el draft al user store (incluido el token que dejó el AuthStep) y
 * marca el onboarding como completo. El backend NO tiene `POST /v1/user/onboard`:
 * el flag `onboarding_completed` se maneja client-side, y nombre/mood/modos
 * quedan en el user store (no hay endpoint para persistirlos todavía).
 */
export function useCompleteOnboarding() {
  const router = useRouter();
  const [isPending, setIsPending] = useState(false);

  const complete = useCallback(() => {
    setIsPending(true);
    const draft = useOnboardingStore.getState();
    const user = useUserStore.getState();

    // Cierre local (no hay endpoint de onboard): el token ya viene del AuthStep
    // en el draft y acá se commitea al user store, de donde lo lee el cliente API.
    user.setDisplayName(draft.displayName);
    user.setMood(draft.mood, draft.moodFreeText);
    user.setInterestedModes(draft.interestedModes as Mode[]);
    if (draft.authedUserId && draft.authedToken) {
      user.setAuth({
        userId: draft.authedUserId,
        token: draft.authedToken,
        isEphemeral: draft.authMode === "ephemeral",
      });
    }
    user.completeOnboarding();
    useOnboardingStore.getState().reset();

    router.replace("/");
  }, [router]);

  return { complete, isPending };
}
