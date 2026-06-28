import { type OnboardRequest, OnboardRequestSchema } from "@ynara/shared-schemas";
import { api } from "../../api";
import type { OnboardingDraft } from "./store";

/**
 * Cierre del onboarding compartido web + mobile (ADR-012). Antes vivía duplicado
 * en `apps/web/.../useCompleteOnboarding.ts` y `apps/mobile/.../useCompleteOnboarding.ts`
 * con mutationFns casi idénticas; acá queda la única fuente de verdad (testeada
 * en `completion.test.ts`). Cada app sigue manejando su `onSuccess` (commit al
 * user store + navegación/celebración) porque eso sí difiere por plataforma.
 *
 * Contrato (reconcile con el backend real): el backend NO tiene un endpoint
 * `onboard`; marca el onboarding con `PATCH /v1/users/me` (body `UserUpdate`
 * snake_case, `extra='forbid'`, solo `{display_name?, onboarding_completed?,
 * retention_sensitive_days?}` → `200 UserOut`). Por eso al backend SOLO le
 * mandamos `{ display_name, onboarding_completed: true }`; `mood`/`moodFreeText`/
 * `interestedModes`/`a11y`/sobre-vos no tienen columna server-side y quedan
 * client-side. La response (`UserOut`) no se consume: el caller sigue con el
 * draft local validado que devolvemos acá y commitea al user store en su
 * `onSuccess`.
 *
 * AUTH: durante el onboarding el token vive en el draft (`draft.authedToken`),
 * NO en el user store (`setAuth` recién corre en el `onSuccess` del caller,
 * DESPUÉS de este PATCH), y el cliente HTTP no adjunta el Bearer solo todavía.
 * Por eso pasamos el token EXPLÍCITO acá, igual que `me(token)`: sin esto el
 * backend real devuelve 401. Guard antes del PATCH para fallar con mensaje
 * claro si el draft perdió la sesión.
 */

/**
 * Preferencias de a11y que el caller lee de su a11y store (fuente canónica de
 * a11y, no el draft). Mismo shape que `A11yPrefsSchema` de shared-schemas.
 */
export type OnboardingA11yPrefs = {
  textSize: "sm" | "md" | "lg";
  highContrast: boolean;
  motion: "auto" | "reduce" | "normal";
};

/**
 * Arma el payload del onboarding desde el draft + a11y, lo valida localmente y
 * persiste el flag de onboarding con `PATCH /v1/users/me`. Devuelve el payload
 * validado para que el caller lo commitee al user store en su `onSuccess`.
 *
 * @throws si la validación falla (primer issue del schema) o si el draft no
 * tiene token de sesión.
 */
export async function submitOnboarding(params: {
  draft: OnboardingDraft;
  a11y: OnboardingA11yPrefs;
}): Promise<OnboardRequest> {
  const { draft, a11y } = params;
  const payload = {
    displayName: draft.displayName,
    mood: draft.mood,
    moodFreeText: draft.moodFreeText.length > 0 ? draft.moodFreeText : undefined,
    interestedModes: draft.interestedModes,
    a11y: {
      textSize: a11y.textSize,
      highContrast: a11y.highContrast,
      motion: a11y.motion,
    },
  };
  const parsed = OnboardRequestSchema.safeParse(payload);
  if (!parsed.success) {
    const first = parsed.error.issues[0];
    throw new Error(first?.message ?? "Revisá tus datos.");
  }
  if (!draft.authedToken) {
    throw new Error("Sesión inválida. Volvé a empezar el onboarding.");
  }
  // El backend solo persiste `display_name` y la flag; traducimos
  // camelCase→snake_case y mandamos SOLO lo que `UserUpdate` acepta
  // (extra='forbid' rechazaría cualquier campo de más). La response `UserOut`
  // no se consume: el caller sigue con el draft local validado.
  await api.patch<unknown>(
    "/v1/users/me",
    { display_name: parsed.data.displayName, onboarding_completed: true },
    { headers: { Authorization: `Bearer ${draft.authedToken}` } },
  );
  return parsed.data;
}
