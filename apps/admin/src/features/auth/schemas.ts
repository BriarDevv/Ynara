import { z } from "zod";

/**
 * Contrato REAL de auth admin (`/v1/auth/*`, backend FastAPI).
 *
 * Mirror 1:1 de los Pydantic verificados del backend — snake_case, igual que el
 * resto de los contratos del panel (`features/<f>/schemas.ts`). Regla
 * "Pydantic gana, Zod sigue": estos shapes copian lo que el backend devuelve.
 *
 * ⚠️ NO usar `@ynara/shared-schemas/auth` acá: ese módulo es **provisional**
 * (camelCase `token`/`userId`/`expiresAt`, pendiente de acuerdo con backend) y
 * NO matchea el contrato real (`access_token`/`token_type`/`refresh_token`). El
 * wire del panel se cablea contra estos schemas, no contra el provisional.
 *
 * Privacidad (reglas #2/#4): `MeOut` trae solo la identidad del operador para
 * pintar el Topbar. El eje de autorización es `is_admin`, que **no** vive en
 * `UserOut`: el gate real lo hace el backend devolviendo 401 en `/v1/admin/*`
 * si el user no es admin (ver `useLogin`/`providers`).
 */

/** Body de `POST /v1/auth/token`. Validado por el form (react-hook-form). */
export const LoginRequest = z.object({
  email: z.string().email("Email inválido"),
  password: z.string().min(1, "Ingresá tu contraseña"),
});
export type LoginRequestT = z.infer<typeof LoginRequest>;

/**
 * Respuesta de `POST /v1/auth/token` (`TokenOut`). `token_type` es siempre
 * `"bearer"`; `refresh_token` puede venir `null` (sesión sin refresh).
 */
export const TokenOut = z.object({
  access_token: z.string().min(1),
  token_type: z.literal("bearer"),
  refresh_token: z.string().nullable().optional(),
});
export type TokenOutT = z.infer<typeof TokenOut>;

/**
 * Respuesta de `GET /v1/auth/me` (`UserOut`). Identidad del operador logueado.
 * NO incluye `is_admin` (el backend no lo expone acá): la autorización admin se
 * resuelve por el 401 de `/v1/admin/*`, no por este payload.
 */
export const MeOut = z.object({
  id: z.string(),
  email: z.string(),
  display_name: z.string(),
  onboarding_completed: z.boolean(),
  retention_sensitive_days: z.number().int(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type MeOutT = z.infer<typeof MeOut>;
