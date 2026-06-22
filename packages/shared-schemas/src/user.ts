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

/*
 * Perfil del backend — mirror de `/v1/users/me` (Tanda 1, ya en `main`). "Pydantic
 * gana, Zod sigue": si el backend cambia el contrato, se corrige este mirror en el
 * mismo PR. Tabla `users` operativa (no sagrada).
 */

/** Días de retención de memoria sensible. Pydantic: `int (30..365)`. */
export const RetentionDaysSchema = z.number().int().min(30).max(365);

/**
 * Body de `PATCH /v1/users/me` — update parcial del perfil propio. Todos los
 * campos opcionales (`exclude_none` en el backend: un PATCH sin campos es no-op).
 * `display_name` reutiliza la validación del onboarding (más estricta que el
 * `<=40` del backend: tightening de cliente sobre lo que se manda).
 */
export const UserUpdateSchema = z.object({
  display_name: DisplayNameSchema.optional(),
  onboarding_completed: z.boolean().optional(),
  retention_sensitive_days: RetentionDaysSchema.optional(),
});
export type UserUpdate = z.infer<typeof UserUpdateSchema>;

/**
 * Respuesta de `PATCH /v1/users/me` (y `GET /v1/auth/me`): `UserOut`. **Nunca**
 * incluye `password_hash`. `retention_sensitive_days` va como entero pelado (la
 * respuesta refleja el valor guardado; el rango lo garantiza el backend).
 *
 * `display_name` es nullable: el modelo Pydantic (`User.display_name: str | None`)
 * puede devolver `null` cuando el usuario todavía no completó el paso de nombre
 * (ej. registro efímero sin onboarding). "Pydantic gana, Zod sigue."
 */
export const UserOutSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  display_name: z.string().nullable(),
  onboarding_completed: z.boolean(),
  retention_sensitive_days: z.number().int(),
  created_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
});
export type UserOut = z.infer<typeof UserOutSchema>;
