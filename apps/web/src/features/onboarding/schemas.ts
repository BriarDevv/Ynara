import {
  A11yPrefsSchema,
  ApiErrorBodySchema,
  AuthResponseSchema,
  DisplayNameSchema,
  LoginRequestSchema,
  ModeSchema,
  OnboardRequestSchema,
  SignupRequestSchema,
} from "@ynara/shared-schemas";
import { z } from "zod";

/*
 * Re-exports + schemas locales del onboarding.
 *
 * Los Zod que tienen contraparte en backend (auth, onboard, displayName,
 * a11y) viven en `packages/shared-schemas`. Acá sólo lo específico de
 * la UI del onboarding: el step-by-step del store, etc.
 */

// ============================================================
// Step 2 · Nombre
// ============================================================

export const NameFormSchema = z.object({
  displayName: DisplayNameSchema,
});
export type NameFormValues = z.infer<typeof NameFormSchema>;

// ============================================================
// Step 3 · Día (mood)
// ============================================================

/**
 * Máximo de moods seleccionables a la vez (plan §4.4). El límite se
 * comparte con la UI: el OptionCard del mood #3 se deshabilita cuando
 * ya hay 2 elegidos.
 */
export const MAX_MOODS = 2;
/** Máximo de caracteres del textarea libre (plan §4.4 + OnboardRequest). */
export const MAX_MOOD_FREE_TEXT = 160;

export const MoodFormSchema = z.object({
  mood: z.array(z.string()).max(MAX_MOODS),
  moodFreeText: z.string().max(MAX_MOOD_FREE_TEXT),
});
export type MoodFormValues = z.infer<typeof MoodFormSchema>;

// ============================================================
// Step 4 · Modos
// ============================================================

export const ModesFormSchema = z.object({
  interestedModes: z.array(ModeSchema).min(1, "Elegí al menos uno"),
});
export type ModesFormValues = z.infer<typeof ModesFormSchema>;

// ============================================================
// Re-export para que features/onboarding no tenga que importar dos paquetes
// ============================================================

export type {
  A11yPrefs,
  ApiErrorBody,
  AuthResponse,
  Mode,
  OnboardRequest,
} from "@ynara/shared-schemas";
export {
  A11yPrefsSchema,
  ApiErrorBodySchema,
  AuthResponseSchema,
  DisplayNameSchema,
  LoginRequestSchema,
  ModeSchema,
  OnboardRequestSchema,
  SignupRequestSchema,
};
