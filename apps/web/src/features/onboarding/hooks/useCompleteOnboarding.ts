"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { submitOnboarding } from "@ynara/core/features/onboarding";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import type { ModeId } from "@/components/ui/modes";
import { ApiError } from "@/lib/api";
import { qk } from "@/lib/queryKeys";
import { useA11yStore } from "@/stores/a11y";
import { useActiveModeStore } from "@/stores/mode";
import { useUserStore } from "@/stores/user";
import type { ApiErrorBody } from "../schemas";
import { useOnboardingStore } from "../store";

type Returns = {
  /** Llamar desde A11yStep al submit. Dispara el flujo entero. */
  complete: () => void;
  /** True mientras el POST corre. UI puede deshabilitar el botón. */
  isPending: boolean;
  /** True una vez que la mutation pasó. UI cambia a CelebrationOutro. */
  isCelebrating: boolean;
  /** Mensaje de error si la mutation falla. */
  error: string | null;
};

/**
 * Orquesta el cierre del onboarding:
 *  1. `submitOnboarding` (@ynara/core): valida el draft con `OnboardRequestSchema`
 *     y persiste el flag con `PATCH /v1/users/me`. Lógica compartida con mobile
 *     (única fuente de verdad, testeada en core); el contrato del backend vive
 *     en su docstring.
 *  2. Traslada datos al `useUserStore`.
 *  3. Resetea el draft del onboarding.
 *  4. Setea `isCelebrating=true` para que la UI monte `CelebrationOutro`.
 *  5. Cuando `CelebrationOutro` llama `triggerOutroComplete()`, navega
 *     a `/hoy?welcome=true` (la tab Hoy del app shell; el query param dispara
 *     el toast de bienvenida que `HoyView` consume y limpia).
 *
 * El a11y vive en `useA11yStore` (D3), no en el draft.
 */
export function useCompleteOnboarding(): Returns & {
  /** Callback para que `CelebrationOutro` cierre la navegación al desmontar. */
  triggerOutroComplete: () => void;
} {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [isCelebrating, setIsCelebrating] = useState(false);

  const draft = useOnboardingStore.getState;
  const a11y = useA11yStore.getState;

  const mutation = useMutation({
    // El armado/validación/PATCH vive en `submitOnboarding` (@ynara/core), única
    // fuente de verdad compartida con mobile (testeada en core). El `onSuccess`
    // de abajo es lo específico de web (commit al user store, invalidación de
    // caches, celebración, navegación).
    mutationFn: () =>
      submitOnboarding({
        draft: draft(),
        a11y: {
          textSize: a11y().textSize,
          highContrast: a11y().highContrast,
          motion: a11y().motion,
        },
      }),
    onSuccess: (data) => {
      const d = draft();
      if (!d.authedUserId || !d.authedToken) {
        setError("Sesión inválida. Volvé a empezar el onboarding.");
        return;
      }
      // El onboarding solo crea cuentas reales (signup/login). El backend
      // hardcodea is_ephemeral=False y el front no consume ese flag.
      useUserStore.getState().setAuth({
        userId: d.authedUserId,
        token: d.authedToken,
      });
      useUserStore.getState().setDisplayName(data.displayName);
      useUserStore.getState().setMood(data.mood, data.moodFreeText ?? "");
      useUserStore.getState().setInterestedModes(data.interestedModes as ModeId[]);
      // Sembrar el modo activo global con el PRIMER modo de interés elegido en el
      // onboarding. Sin esto, el override de `useActiveModeStore` nunca se siembra
      // y `useActiveMode` cae siempre a `interestedModes[0]` por derivación; el
      // resultado visible era que el modo activo arrancaba fijo en 'productividad'.
      const [primary] = data.interestedModes;
      if (primary) useActiveModeStore.getState().setMode(primary as ModeId);
      // Sobre-vos: igual que mood/modes, no tiene columna en el backend y queda
      // client-side. Se lee del draft (no del payload validado, que solo lleva
      // lo que `OnboardRequestSchema` conoce).
      useUserStore.getState().setProfileContext({
        dedication: d.dedication,
        studyWhat: d.studyWhat,
        workWhat: d.workWhat,
        purpose: d.purpose,
        interests: d.interests,
      });
      useUserStore.getState().completeOnboarding();
      useOnboardingStore.getState().reset();
      // El perfil "me" vive en el user store (no hay query "me" en core), pero
      // este onSuccess cruza el borde de identidad: limpiamos los caches por
      // usuario (hoy/agenda/memoria/sesiones) para que las vistas a las que el
      // user navega tras el outro pidan datos frescos en vez de mostrar cache de
      // un estado previo. Invalidación por prefijo (TanStack matchea por inicio).
      queryClient.invalidateQueries({ queryKey: qk.today.tasks() });
      queryClient.invalidateQueries({ queryKey: qk.today.suggestions() });
      queryClient.invalidateQueries({ queryKey: qk.today.recap() });
      queryClient.invalidateQueries({ queryKey: qk.agenda.all() });
      queryClient.invalidateQueries({ queryKey: qk.memory.all() });
      queryClient.invalidateQueries({ queryKey: qk.sessions.all() });
      setIsCelebrating(true);
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        const body = err.body as Partial<ApiErrorBody> | null;
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

  const triggerOutroComplete = useCallback(() => {
    router.replace("/hoy?welcome=true");
  }, [router]);

  return {
    complete,
    isPending: mutation.isPending,
    isCelebrating,
    error,
    triggerOutroComplete,
  };
}
