"use client";

import { useMutation } from "@tanstack/react-query";
import { OnboardResponseSchema } from "@ynara/shared-schemas";
import { useCallback } from "react";
import type { ModeId } from "@/components/ui/modes";
import { api } from "@/lib/api";
import { useA11yStore } from "@/stores/a11y";
import { useUserStore } from "@/stores/user";
import { OnboardRequestSchema } from "../schemas";
import { useOnboardingStore } from "../store";

/**
 * Cierra el onboarding: arma el `OnboardRequest` con el draft + las
 * preferencias de a11y, lo manda al backend (mock MSW por ahora) y, si
 * sale OK, traslada el draft de `sessionStorage` (useOnboardingStore) al
 * perfil persistente en `localStorage` (useUserStore) y lo marca como
 * completado.
 *
 * La navegación al /home la maneja el componente que lo consume
 * (CelebrationOutro), para poder respetar la animación de 1.5s del outro.
 */
export function useCompleteOnboarding() {
  const resetDraft = useOnboardingStore((s) => s.reset);

  const mutation = useMutation({
    mutationFn: async () => {
      // Leo el estado fresco con getState() (no via hook) para no suscribir
      // el outro a cada cambio de los stores y evitar stale closures.
      const draft = useOnboardingStore.getState();
      const a11y = useA11yStore.getState();
      const user = useUserStore.getState();

      const payload = OnboardRequestSchema.parse({
        displayName: draft.displayName,
        mood: draft.mood,
        moodFreeText: draft.moodFreeText || undefined,
        interestedModes: draft.interestedModes,
        a11y: {
          textSize: a11y.textSize,
          highContrast: a11y.highContrast,
          motion: a11y.motion,
        },
      });
      const raw = await api.post<unknown>("/v1/user/onboard", payload);
      const response = OnboardResponseSchema.parse(raw);

      // Traslado draft → perfil persistente. Sólo tras OK del backend.
      //
      // OJO: NO llamamos `completeOnboarding()` acá a propósito. Ese flag
      // dispara el guard del layout (`if (completed) return null` +
      // redirect a /home), que desmontaría el CelebrationOutro antes de
      // que reproduzca su animación. El flag lo flipea la /home al montar
      // (ve `userId && !onboardingCompleted`), una vez que ya salimos del
      // árbol del onboarding.
      user.setAuth({
        userId: draft.authedUserId ?? `ephemeral-${response.onboardedAt}`,
        token: draft.authedToken ?? "",
        isEphemeral: draft.authMode === "ephemeral",
      });
      user.setDisplayName(draft.displayName);
      user.setMood(draft.mood, draft.moodFreeText);
      user.setInterestedModes(payload.interestedModes as ModeId[]);
      return response;
    },
  });

  // `mutation.mutate` es referencialmente estable en TanStack Query, así
  // que `complete` también lo es: el effect del outro que lo dispara no
  // se re-ejecuta en cada render (y no reinicia el timer de la animación).
  const complete = useCallback(() => mutation.mutate(), [mutation.mutate]);

  return {
    complete,
    isPending: mutation.isPending,
    isError: mutation.isError,
    isSuccess: mutation.isSuccess,
    /** Limpia el draft de sessionStorage. Llamar tras navegar al home. */
    clearDraft: resetDraft,
  };
}
