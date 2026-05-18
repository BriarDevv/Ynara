import { z } from "zod";

/*
 * Shapes provisionales del contrato de auth.
 *
 * SHAPE PROVISIONAL — pendiente de acuerdo con backend (ver issue
 * BriarDevv/Ynara#6). Cuando @BriarDevv cierre el contrato y aparezcan
 * los Pydantic en apps/backend/app/schemas/, mirrorear acá en el mismo
 * PR de Pydantic (regla AI-GUIDELINES "Pydantic gana, Zod sigue").
 */

// ============================================================
// Request shapes
// ============================================================

export const SignupRequestSchema = z.object({
  email: z.string().email("Email inválido"),
  password: z
    .string()
    .min(8, "La contraseña debe tener al menos 8 caracteres")
    .max(128, "La contraseña es demasiado larga"),
});
export type SignupRequest = z.infer<typeof SignupRequestSchema>;

export const LoginRequestSchema = z.object({
  email: z.string().email("Email inválido"),
  password: z.string().min(1, "Ingresá tu contraseña"),
});
export type LoginRequest = z.infer<typeof LoginRequestSchema>;

// ============================================================
// Response shapes
// ============================================================

export const AuthResponseSchema = z.object({
  token: z.string().min(1),
  userId: z.string().min(1),
  /** ISO 8601. Opcional hasta acuerdo final con backend. */
  expiresAt: z.string().datetime().optional(),
});
export type AuthResponse = z.infer<typeof AuthResponseSchema>;

// ============================================================
// Error shape (uniforme para 4xx)
// ============================================================

export const ApiErrorBodySchema = z.object({
  error: z.string(),
  detail: z.string(),
  /** Campo del form al que aplica, si corresponde (form binding). */
  field: z.string().optional(),
});
export type ApiErrorBody = z.infer<typeof ApiErrorBodySchema>;
