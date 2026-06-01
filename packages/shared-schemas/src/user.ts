import { z } from "zod";
import { ModeSchema } from "./modes";

/*
 * Schemas del onboarding completo. Algunos campos se completan en Sesión 4
 * del plan; los dejo definidos acá para que el resto del onboarding pueda
 * importarlos sin futuro refactor.
 */

export const DisplayNameSchema = z
  .string()
  .trim()
  .min(2, "Mínimo 2 caracteres")
  .max(40, "Máximo 40 caracteres")
  .regex(/^[\p{L}\p{M}'\- ]+$/u, "Sólo letras, espacios, apóstrofes o guiones");

export const A11yPrefsSchema = z.object({
  textSize: z.enum(["sm", "md", "lg"]),
  highContrast: z.boolean(),
  motion: z.enum(["auto", "reduce", "normal"]),
});
export type A11yPrefs = z.infer<typeof A11yPrefsSchema>;

export const OnboardRequestSchema = z.object({
  displayName: DisplayNameSchema,
  mood: z.array(z.string()).max(2),
  moodFreeText: z.string().max(160).optional(),
  interestedModes: z.array(ModeSchema).min(1, "Elegí al menos uno"),
  a11y: A11yPrefsSchema,
});
export type OnboardRequest = z.infer<typeof OnboardRequestSchema>;

export const OnboardResponseSchema = z.object({
  ok: z.literal(true),
  onboardedAt: z.number(),
});
export type OnboardResponse = z.infer<typeof OnboardResponseSchema>;
