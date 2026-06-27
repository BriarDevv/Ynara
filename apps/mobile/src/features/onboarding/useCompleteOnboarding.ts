import { useMutation } from "@tanstack/react-query";
import { type Mode, OnboardRequestSchema, type UserOut } from "@ynara/shared-schemas";
import { useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { ApiError, api } from "@/lib/api";
import { useA11yStore } from "@/stores/a11y";
import { useOnboardingStore } from "@/stores/onboarding";
import { useOnboardingStepStore } from "@/stores/onboardingStep";
import { useUserStore } from "@/stores/user";

type Returns = {
  /** Llamar desde A11yStep al submit. Dispara el flujo entero. */
  complete: () => void;
  /** True mientras el PATCH corre. La UI deshabilita el botón. */
  isPending: boolean;
  /** Mensaje de error si la mutation falla. */
  error: string | null;
};

/**
 * Cierre del onboarding (mobile). Espeja el contrato de web
 * (`apps/web/.../useCompleteOnboarding.ts`): valida el draft con
 * `OnboardRequestSchema` y persiste el flag de onboarding con
 * `PATCH /v1/users/me`. Antes era una función síncrona que solo escribía
 * stores; ahora también persiste `onboarding_completed` server-side (paridad
 * con web), si no la cuenta quedaba con el onboarding sin marcar en el backend.
 *
 * Contrato: el backend NO tiene endpoint `onboard`; marca el onboarding con
 * `PATCH /v1/users/me` (body `UserUpdate` snake_case, `extra='forbid'`, solo
 * `{display_name?, onboarding_completed?, retention_sensitive_days?}`). Por eso
 * al backend SOLO le mandamos `{ display_name, onboarding_completed: true }`;
 * `mood`/`moodFreeText`/`interestedModes`/`a11y` no tienen columna server-side y
 * quedan client-side (`useUserStore` + `useA11yStore`).
 */
export function useCompleteOnboarding(): Returns {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const d = useOnboardingStore.getState();
      const a = useA11yStore.getState();
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
      // AUTH (paridad con web): durante el onboarding el token vive en el draft
      // (`d.authedToken`), NO en `useUserStore` (`setAuth` recién corre en
      // `onSuccess`, DESPUÉS de este PATCH). Por eso pasamos el token EXPLÍCITO
      // acá: el cliente HTTP no adjunta el Bearer solo todavía y sin esto el
      // backend real devuelve 401. Guard antes del PATCH para fallar con mensaje
      // claro si el draft perdió la sesión.
      if (!d.authedToken) {
        throw new Error("Sesión inválida. Volvé a empezar el onboarding.");
      }
      // El backend solo persiste `display_name` y la flag; traducimos
      // camelCase→snake_case y mandamos SOLO lo que `UserUpdate` acepta
      // (extra='forbid' rechazaría cualquier campo de más). La response
      // `UserOut` no se consume: `onSuccess` sigue con el draft local validado.
      await api.patch<UserOut>(
        "/v1/users/me",
        { display_name: parsed.data.displayName, onboarding_completed: true },
        { headers: { Authorization: `Bearer ${d.authedToken}` } },
      );
      return parsed.data;
    },
    onSuccess: (data) => {
      const d = useOnboardingStore.getState();
      if (!d.authedUserId || !d.authedToken) {
        setError("Sesión inválida. Volvé a empezar el onboarding.");
        return;
      }
      const user = useUserStore.getState();
      // El onboarding solo crea cuentas reales (signup): ya no hay entrada
      // efímera, así que isEphemeral va en false. (El flag existe en el backend
      // pero el front todavía no lo consume.)
      user.setAuth({
        userId: d.authedUserId,
        token: d.authedToken,
        isEphemeral: false,
      });
      user.setDisplayName(data.displayName);
      user.setMood(data.mood, data.moodFreeText ?? "");
      user.setInterestedModes(data.interestedModes as Mode[]);
      // Sobre-vos: igual que mood/modos, no tiene columna en el backend y queda
      // client-side. Se lee del draft (no del payload validado, que solo lleva
      // lo que `OnboardRequestSchema` conoce).
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
