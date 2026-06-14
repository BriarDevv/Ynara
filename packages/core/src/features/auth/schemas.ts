import { z } from "zod";

/*
 * Schemas de auth contra el backend REAL (mirror de los Pydantic de
 * apps/backend/app/schemas, rutas /v1/auth/*). Distinto del contrato
 * PROVISIONAL de @ynara/shared-schemas (auth.ts: signup/login con
 * `{ token, userId }`), que sigue vivo para los mocks de la web hasta la
 * reconciliación (BriarDevv/Ynara#6, "Pydantic gana, Zod sigue").
 *
 * Contrato real:
 * - POST /v1/auth/register {email, password, display_name?} -> user (SIN token)
 * - POST /v1/auth/token    {email, password}               -> access/refresh
 * - GET  /v1/auth/me                                        -> user
 */

/** User que devuelven `register` y `GET /v1/auth/me`. */
export const AuthUserSchema = z.object({
  id: z.string().min(1),
  email: z.string(),
  display_name: z.string().nullable().optional(),
  is_ephemeral: z.boolean(),
  onboarding_completed: z.boolean(),
});
export type AuthUser = z.infer<typeof AuthUserSchema>;

/** Respuesta de `POST /v1/auth/token`. */
export const TokenResponseSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.string(),
  refresh_token: z.string().min(1),
});
export type TokenResponse = z.infer<typeof TokenResponseSchema>;
