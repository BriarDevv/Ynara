"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import type { ModeId } from "@/components/ui/modes";
import { ApiError, api } from "@/lib/api";
import { useA11yStore } from "@/stores/a11y";
import { useUserStore } from "@/stores/user";
import { type ApiErrorBody, OnboardRequestSchema } from "../schemas";
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
 *  1. Valida el draft completo con `OnboardRequestSchema`.
 *  2. POST `/v1/user/onboard`.
 *  3. Traslada datos al `useUserStore` (incluyendo `isEphemeral`).
 *  4. Resetea el draft del onboarding.
 *  5. Setea `isCelebrating=true` para que la UI monte `CelebrationOutro`.
 *  6. Cuando `CelebrationOutro` llama `triggerOutroComplete()`, navega
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
  const [error, setError] = useState<string | null>(null);
  const [isCelebrating, setIsCelebrating] = useState(false);

  const draft = useOnboardingStore.getState;
  const a11y = useA11yStore.getState;

  const mutation = useMutation({
    mutationFn: async () => {
      const d = draft();
      const a = a11y();
      const payload = {
        displayName: d.displayName,
        mood: d.mood,
        moodFreeText: d.moodFreeText.length > 0 ? d.moodFreeText : undefined,
        interestedModes: d.interestedModes,
        a11y: {
          textSize: a.textSize,
          highContrast: a.highContrast,
          motion: a.motion,
        },
      };
      const parsed = OnboardRequestSchema.safeParse(payload);
      if (!parsed.success) {
        const first = parsed.error.issues[0];
        throw new Error(first?.message ?? "Revisá tus datos.");
      }
      await api.post<unknown>("/v1/user/onboard", parsed.data);
      return parsed.data;
    },
    onSuccess: (data) => {
      const d = draft();
      if (!d.authedUserId || !d.authedToken) {
        setError("Sesión inválida. Volvé a empezar el onboarding.");
        return;
      }
      // D4 (bloqueante): propagar isEphemeral al user store.
      useUserStore.getState().setAuth({
        userId: d.authedUserId,
        token: d.authedToken,
        isEphemeral: d.authMode === "ephemeral",
      });
      useUserStore.getState().setDisplayName(data.displayName);
      useUserStore.getState().setMood(data.mood, data.moodFreeText ?? "");
      useUserStore.getState().setInterestedModes(data.interestedModes as ModeId[]);
      useUserStore.getState().completeOnboarding();
      useOnboardingStore.getState().reset();
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
