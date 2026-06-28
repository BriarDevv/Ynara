import { type OnboardingIntake, OnboardingIntakeSchema } from "@ynara/shared-schemas";
import { api } from "../../api";
import type { OnboardingDraft } from "./store";

/**
 * Cierre del onboarding compartido web + mobile (ADR-012). Antes vivía duplicado
 * en `apps/web/.../useCompleteOnboarding.ts` y `apps/mobile/.../useCompleteOnboarding.ts`
 * con mutationFns casi idénticas; acá queda la única fuente de verdad (testeada
 * en `completion.test.ts`). Cada app sigue manejando su `onSuccess` (commit al
 * user store + navegación/celebración) porque eso sí difiere por plataforma.
 *
 * Contrato (ADR-026, G6): el intake completo viaja a `POST /v1/onboarding`
 * (snake_case en el wire). El backend persiste lo **OPERATIVO** (`display_name`
 * + `interested_modes` + `a11y` → `users.preferences`) y marca
 * `onboarding_completed`. `mood`/`mood_free_text`/`about` (sobre-vos) viajan en el
 * body pero son **memory-bound**: el backend los acepta/valida pero NO los
 * persiste todavía (seed de memoria = G4, SAGRADO). La response (`UserOut`) no se
 * consume: el caller sigue con el draft local validado que devolvemos acá y
 * commitea al user store en su `onSuccess`.
 *
 * `time_zone` NO va en el intake (ADR-026 §1: el contrato no lo incluye; queda en
 * `PATCH /v1/users/me`). Se captura con un PATCH **best-effort** DESPUÉS del POST:
 * el onboarding ya quedó completo aunque ese PATCH falle, así que no bloquea el
 * cierre (la cuenta queda en el default del backend y se re-setea en ajustes).
 *
 * AUTH: durante el onboarding el token vive en el draft (`draft.authedToken`),
 * NO en el user store (`setAuth` recién corre en el `onSuccess` del caller,
 * DESPUÉS de este POST), y el cliente HTTP no adjunta el Bearer solo todavía.
 * Por eso pasamos el token EXPLÍCITO acá, igual que `me(token)`: sin esto el
 * backend real devuelve 401. Guard antes del POST para fallar con mensaje
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
 * Arma el intake del onboarding desde el draft + a11y, lo valida localmente y lo
 * persiste con `POST /v1/onboarding`. Captura el huso del browser con un PATCH
 * best-effort aparte. Devuelve el intake validado (camelCase) para que el caller
 * lo commitee al user store en su `onSuccess`.
 *
 * @throws si la validación falla (primer issue del schema) o si el draft no
 * tiene token de sesión. Un fallo del PATCH de huso NO hace throw (best-effort).
 */
export async function submitOnboarding(params: {
  draft: OnboardingDraft;
  a11y: OnboardingA11yPrefs;
}): Promise<OnboardingIntake> {
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
    // Sobre-vos: campos planos del draft → objeto `about` (ADR-026). Se manda
    // siempre (memory-bound): el backend lo acepta/valida pero lo descarta hasta
    // G4. `dedication` puede quedar sin elegir (null); los free-text default "".
    about: {
      dedication: draft.dedication,
      studyWhat: draft.studyWhat,
      workWhat: draft.workWhat,
      purpose: draft.purpose,
      interests: draft.interests,
    },
  };
  const parsed = OnboardingIntakeSchema.safeParse(payload);
  if (!parsed.success) {
    const first = parsed.error.issues[0];
    throw new Error(first?.message ?? "Revisá tus datos.");
  }
  if (!draft.authedToken) {
    throw new Error("Sesión inválida. Volvé a empezar el onboarding.");
  }
  const auth = { headers: { Authorization: `Bearer ${draft.authedToken}` } };
  const d = parsed.data;
  // POST /v1/onboarding (ADR-026): intake completo, camelCase→snake_case en el
  // wire. El backend persiste lo OPERATIVO (display_name + interested_modes +
  // a11y → users.preferences) y marca onboarding_completed; mood/about viajan
  // pero se descartan hasta G4 (seed de memoria, SAGRADO). La response (UserOut)
  // no se consume: el caller sigue con el intake local validado.
  await api.post<unknown>(
    "/v1/onboarding",
    {
      display_name: d.displayName,
      interested_modes: d.interestedModes,
      a11y: {
        text_size: d.a11y.textSize,
        high_contrast: d.a11y.highContrast,
        motion: d.a11y.motion,
      },
      mood: d.mood,
      mood_free_text: d.moodFreeText ?? null,
      // `about` es nullable en el contrato (Pydantic `AboutYou | None`); el FE
      // hoy siempre lo arma desde el draft, pero el ternario respeta el tipo y
      // manda `null` si alguna vez viniera sin sobre-vos.
      about: d.about
        ? {
            dedication: d.about.dedication,
            study_what: d.about.studyWhat,
            work_what: d.about.workWhat,
            purpose: d.about.purpose,
            interests: d.about.interests,
          }
        : null,
    },
    auth,
  );
  // time_zone: huso del browser (IANA), fuera del intake (ADR-026 §1 → vive en
  // PATCH /v1/users/me). Best-effort DESPUÉS del POST: el onboarding ya quedó
  // completo, así que un fallo acá NO debe romper el cierre (se traga el error;
  // la cuenta queda en el default del backend y se re-setea en ajustes). Guard
  // por si el runtime no resuelve un timeZone: en ese caso ni se intenta.
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  if (timeZone) {
    try {
      await api.patch<unknown>("/v1/users/me", { time_zone: timeZone }, auth);
    } catch {
      // Best-effort: el huso es secundario al cierre del onboarding (ver arriba).
    }
  }
  return parsed.data;
}
