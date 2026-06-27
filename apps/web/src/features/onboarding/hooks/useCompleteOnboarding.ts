"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { UserOut } from "@ynara/shared-schemas";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import type { ModeId } from "@/components/ui/modes";
import { ApiError, api } from "@/lib/api";
import { qk } from "@/lib/queryKeys";
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
 *  1. Valida el draft completo con `OnboardRequestSchema` (validación LOCAL).
 *  2. `PATCH /v1/users/me` con `{ display_name, onboarding_completed: true }`.
 *  3. Traslada datos al `useUserStore` (incluyendo `isEphemeral`).
 *  4. Resetea el draft del onboarding.
 *  5. Setea `isCelebrating=true` para que la UI monte `CelebrationOutro`.
 *  6. Cuando `CelebrationOutro` llama `triggerOutroComplete()`, navega
 *     a `/hoy?welcome=true` (la tab Hoy del app shell; el query param dispara
 *     el toast de bienvenida que `HoyView` consume y limpia).
 *
 * Contrato (reconcile con el backend real): el backend NO tiene un endpoint
 * `onboard`; marca el onboarding con `PATCH /v1/users/me` (body `UserUpdate`
 * snake_case, `extra='forbid'`, solo `{display_name?, onboarding_completed?,
 * retention_sensitive_days?}` → `200 UserOut`). Por eso al backend SOLO le
 * mandamos `{ display_name, onboarding_completed: true }`; `mood`/`moodFreeText`/
 * `interestedModes`/`a11y` no tienen columna server-side y quedan client-side
 * (`useUserStore` + `useA11yStore`). La response (`UserOut`) no se consume: el
 * flujo de celebración sigue con el draft local validado.
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
      // El backend solo persiste `display_name` y la flag de onboarding; el
      // resto del draft (mood/interestedModes/a11y) no tiene columna y queda
      // client-side. Traducimos camelCase→snake_case y mandamos SOLO lo que
      // `UserUpdate` acepta (extra='forbid' rechazaría cualquier campo de más).
      // La response `UserOut` no se consume: `onSuccess` sigue con el draft local.
      //
      // AUTH (fix mocks-off): durante el onboarding el token vive en el draft
      // (`d.authedToken`), NO en `useUserStore`, y el cliente HTTP NO adjunta el
      // Bearer solo (perímetro documentado en core/auth/api.ts; `setAuth` recién
      // corre en `onSuccess`, DESPUÉS de este PATCH). Por eso pasamos el token
      // EXPLÍCITO acá, igual que `me(token)`: sin esto el backend real devuelve 401
      // (con mocks on no se notaba porque el handler MSW no valida auth). Guard
      // antes del PATCH para fallar con mensaje claro si el draft perdió la sesión.
      if (!d.authedToken) {
        throw new Error("Sesión inválida. Volvé a empezar el onboarding.");
      }
      await api.patch<UserOut>(
        "/v1/users/me",
        { display_name: parsed.data.displayName, onboarding_completed: true },
        { headers: { Authorization: `Bearer ${d.authedToken}` } },
      );
      return parsed.data;
    },
    onSuccess: (data) => {
      const d = draft();
      if (!d.authedUserId || !d.authedToken) {
        setError("Sesión inválida. Volvé a empezar el onboarding.");
        return;
      }
      // El onboarding solo crea cuentas reales (signup/login): ya no hay entrada
      // efímera client-side, así que isEphemeral va en false. (El flag is_ephemeral
      // existe en el backend pero el front todavía no lo consume.)
      useUserStore.getState().setAuth({
        userId: d.authedUserId,
        token: d.authedToken,
        isEphemeral: false,
      });
      useUserStore.getState().setDisplayName(data.displayName);
      useUserStore.getState().setMood(data.mood, data.moodFreeText ?? "");
      useUserStore.getState().setInterestedModes(data.interestedModes as ModeId[]);
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
