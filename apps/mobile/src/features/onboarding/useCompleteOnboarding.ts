import type { Mode } from "@ynara/shared-schemas";
import { useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { useOnboardingStore } from "@/stores/onboarding";
import { useUserStore } from "@/stores/user";

/**
 * Cierre del onboarding (mobile).
 *
 * IMPORTANTE: por ahora es un cierre LOCAL — traslada el draft al user store y
 * marca el onboarding como completo, SIN el `POST /v1/user/onboard` real (eso
 * llega cuando levantemos el backend; ver TODO). El AuthStep tampoco está
 * todavía, así que normalmente no hay token en el draft.
 */
export function useCompleteOnboarding() {
  const router = useRouter();
  const [isPending, setIsPending] = useState(false);

  const complete = useCallback(() => {
    setIsPending(true);
    const draft = useOnboardingStore.getState();
    const user = useUserStore.getState();

    // TODO(backend): await api.post("/v1/user/onboard", payload) antes de
    // propagar, y manejar el error. Por ahora cierre local.
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
