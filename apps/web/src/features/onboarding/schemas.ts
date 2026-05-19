import {
  A11yPrefsSchema,
  ApiErrorBodySchema,
  AuthResponseSchema,
  DisplayNameSchema,
  LoginRequestSchema,
  ModeSchema,
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
// Re-export para que features/onboarding no tenga que importar dos paquetes
// ============================================================

export type { A11yPrefs, ApiErrorBody, Mode } from "@ynara/shared-schemas";
export {
  A11yPrefsSchema,
  ApiErrorBodySchema,
  AuthResponseSchema,
  DisplayNameSchema,
  LoginRequestSchema,
  ModeSchema,
  SignupRequestSchema,
};
