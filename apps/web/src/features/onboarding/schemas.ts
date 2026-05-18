import {
  A11yPrefsSchema,
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
 * la UI del onboarding: el discriminator de tab auth, el step-by-step
 * del store, etc.
 */

// ============================================================
// Step 1 · Auth — discriminated union para tabs signup/login
// ============================================================

export const AuthFormSchema = z.discriminatedUnion("mode", [
  z.object({ mode: z.literal("signup") }).merge(SignupRequestSchema),
  z.object({ mode: z.literal("login") }).merge(LoginRequestSchema),
]);
export type AuthFormValues = z.infer<typeof AuthFormSchema>;

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

export type { A11yPrefs, Mode } from "@ynara/shared-schemas";
export { A11yPrefsSchema, DisplayNameSchema, ModeSchema, SignupRequestSchema };
