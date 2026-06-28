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

/**
 * @deprecated Usar `OnboardingIntakeSchema`. Era el contrato camelCase que solo
 * gateaba validación local (no había endpoint que lo recibiera); ahora el intake
 * viaja a `POST /v1/onboarding` con el shape extendido (incluye `about`). Se
 * mantiene como base de `OnboardingIntakeSchema` y por compat de re-exports.
 */
export const OnboardRequestSchema = z.object({
  displayName: DisplayNameSchema,
  mood: z.array(z.string()).max(2),
  moodFreeText: z.string().max(160).optional(),
  interestedModes: z.array(ModeSchema).min(1, "Elegí al menos uno"),
  a11y: A11yPrefsSchema,
});
export type OnboardRequest = z.infer<typeof OnboardRequestSchema>;

/**
 * A qué se dedica el usuario (step "sobre-vos"). **Fuente canónica** (mirror del
 * `Literal` de `AboutYou.dedication` en Pydantic). `@ynara/core` re-exporta este
 * tipo para el draft del onboarding en vez de duplicar la unión.
 */
export const DedicationSchema = z.enum(["estudio", "trabajo", "ambos", "otro"]);
export type Dedication = z.infer<typeof DedicationSchema>;

/**
 * "Sobre vos" del onboarding (camelCase, FE-facing). Mirror de `AboutYou`
 * (Pydantic) — el wire es snake_case y lo mapea `submitOnboarding` en
 * `@ynara/core`. Señal **memory-bound**: el backend la acepta/valida pero NO la
 * persiste todavía (seed de memoria = G4, SAGRADO). `dedication` nullable: el
 * step puede dejarse sin elegir. Free-text acotado (anti-inflado, `<=200`).
 */
export const AboutYouSchema = z.object({
  dedication: DedicationSchema.nullable(),
  studyWhat: z.string().max(200),
  workWhat: z.string().max(200),
  purpose: z.string().max(200),
  interests: z.string().max(200),
});
export type AboutYou = z.infer<typeof AboutYouSchema>;

/**
 * Intake completo del onboarding (camelCase, FE-facing). Mirror de
 * `OnboardingIntake` (Pydantic, fuente de verdad; el wire es snake_case) — ADR-026.
 * Es lo que `submitOnboarding` (@ynara/core) valida antes de mapear al wire y
 * mandar a `POST /v1/onboarding`. Reemplaza al `OnboardRequestSchema` huérfano:
 * extiende su shape con `about` (sobre-vos).
 */
export const OnboardingIntakeSchema = OnboardRequestSchema.extend({
  about: AboutYouSchema.nullable(),
});
export type OnboardingIntake = z.infer<typeof OnboardingIntakeSchema>;

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
  // Huso horario IANA del cliente (ej. "America/Argentina/Buenos_Aires"). Acá
  // solo validamos que sea un string no vacío; el formato IANA fuerte lo valida
  // el backend (Pydantic). El onboarding lo inyecta con el huso del browser.
  time_zone: z.string().min(1).optional(),
});
export type UserUpdate = z.infer<typeof UserUpdateSchema>;

/**
 * a11y como vive en `users.preferences` (JSONB) — **snake_case del wire**.
 * Distinto de `A11yPrefsSchema` (camelCase, FE-facing): este espeja lo que el
 * backend ESCRIBE/DEVUELVE en la columna (`A11yPrefs` de Pydantic).
 */
const A11yPrefsWireSchema = z.object({
  text_size: z.enum(["sm", "md", "lg"]),
  high_contrast: z.boolean(),
  motion: z.enum(["auto", "reduce", "normal"]),
});

/**
 * Forma de `users.preferences` (JSONB) que viaja en `UserOut`. Mirror de
 * `UserPreferences` (Pydantic). **Todo opcional**: las filas pre-onboarding
 * tienen `{}` (sin modos ni a11y) y deben validar igual. Lo OPERATIVO del
 * onboarding (modos de interés + a11y) que el FE hidrata en G3. "Pydantic gana,
 * Zod sigue".
 */
export const UserPreferencesSchema = z.object({
  interested_modes: z.array(ModeSchema).optional(),
  a11y: A11yPrefsWireSchema.optional(),
});
export type UserPreferences = z.infer<typeof UserPreferencesSchema>;

/**
 * Respuesta de `PATCH /v1/users/me` (y `GET /v1/auth/me`): `UserOut`. **Nunca**
 * incluye `password_hash`. `retention_sensitive_days` va como entero pelado (la
 * respuesta refleja el valor guardado; el rango lo garantiza el backend).
 *
 * `display_name` es nullable: el modelo Pydantic (`User.display_name: str | None`)
 * puede devolver `null` cuando el usuario todavía no completó el paso de nombre
 * (ej. registro efímero sin onboarding). "Pydantic gana, Zod sigue."
 *
 * `preferences` es la columna JSONB operativa (modos + a11y). Default `{}` para
 * tolerar respuestas sin la clave (defensivo; el backend siempre la manda).
 */
export const UserOutSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  display_name: z.string().nullable(),
  // El backend (UserBase) SIEMPRE serializa estos dos; `.default()` los hace
  // tolerantes a respuestas/fixtures que los omitan (mismo criterio defensivo que
  // `preferences`). `is_ephemeral` es vestigial en el FE pero el backend lo manda;
  // `time_zone` queda disponible para hidratación futura.
  is_ephemeral: z.boolean().default(false),
  onboarding_completed: z.boolean(),
  time_zone: z.string().default("UTC"),
  retention_sensitive_days: z.number().int(),
  preferences: UserPreferencesSchema.default({}),
  created_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
});
export type UserOut = z.infer<typeof UserOutSchema>;
