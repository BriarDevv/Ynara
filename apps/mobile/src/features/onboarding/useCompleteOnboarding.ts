import { useMutation } from "@tanstack/react-query";
import { submitOnboarding } from "@ynara/core/features/onboarding";
import type { Mode } from "@ynara/shared-schemas";
import { useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { ApiError } from "@/lib/api";
import { useA11yStore } from "@/stores/a11y";
import { useOnboardingStore } from "@/stores/onboarding";
import { useOnboardingStepStore } from "@/stores/onboardingStep";
import { useUserStore } from "@/stores/user";

type Returns = {
  /** Llamar desde A11yStep al submit. Dispara el flujo entero. */
  complete: () => void;
  /** True mientras el POST corre. La UI deshabilita el botón. */
  isPending: boolean;
  /** Mensaje de error si la mutation falla. */
  error: string | null;
};

/**
 * Cierre del onboarding (mobile). La validación del draft y el `POST
 * /v1/onboarding` viven en `submitOnboarding` (@ynara/core), compartido con web
 * (única fuente de verdad, testeada en core; el contrato del backend vive en su
 * docstring). Acá queda lo específico de mobile: el `onSuccess` que commitea al
 * user store, resetea los stores de onboarding y navega a "/".
 */
export function useCompleteOnboarding(): Returns {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    // El armado/validación/PATCH vive en `submitOnboarding` (@ynara/core), única
    // fuente de verdad compartida con web (testeada en core). El `onSuccess` de
    // abajo es lo específico de mobile (commit al user store, reset de stores,
    // navegación).
    mutationFn: () => {
      const a = useA11yStore.getState();
      return submitOnboarding({
        draft: useOnboardingStore.getState(),
        a11y: { textSize: a.textSize, highContrast: a.highContrast, motion: a.motion },
      });
    },
    onSuccess: (data) => {
      const d = useOnboardingStore.getState();
      if (!d.authedUserId || !d.authedToken) {
        setError("Sesión inválida. Volvé a empezar el onboarding.");
        return;
      }
      const user = useUserStore.getState();
      // El onboarding solo crea cuentas reales (signup). El backend hardcodea
      // is_ephemeral=False y el front no consume ese flag.
      user.setAuth({
        userId: d.authedUserId,
        token: d.authedToken,
      });
      user.setDisplayName(data.displayName);
      user.setMood(data.mood, data.moodFreeText ?? "");
      user.setInterestedModes(data.interestedModes as Mode[]);
      // Sobre-vos: ahora viaja en el intake (`about`) pero el backend lo descarta
      // hasta G4 (memoria, SAGRADO), así que sigue siendo client-side acá. Se lee
      // del draft (no del payload) porque el commit al user store es local.
      user.setProfileContext({
        dedication: d.dedication,
        studyWhat: d.studyWhat,
        workWhat: d.workWhat,
        purpose: d.purpose,
        interests: d.interests,
      });
      user.completeOnboarding();
      useOnboardingStore.getState().reset();
      useOnboardingStepStore.getState().reset();
      // Mobile no usa query-keys: navega a "/" fresco, sin invalidación de cache.
      router.replace("/");
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        const body = err.body as { detail?: string } | null;
        setError(body?.detail ?? "No pudimos guardar tus datos. Reintentá.");
        return;
      }
      setError(err instanceof Error ? err.message : "Algo no anduvo. Probá de nuevo.");
    },
  });

  const complete = useCallback(() => {
    setError(null);
    mutation.mutate();
  }, [mutation]);

  return { complete, isPending: mutation.isPending, error };
}
