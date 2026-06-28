import { z } from "zod";

/*
 * Schemas de auth contra el backend REAL (mirror de los Pydantic de
 * apps/backend/app/schemas, rutas /v1/auth/*). El user que devuelven
 * `register`/`GET /v1/auth/me` usa la fuente canónica `UserOutSchema`
 * (@ynara/shared-schemas); acá solo vive el shape del token, propio de auth.
 *
 * Contrato real:
 * - POST /v1/auth/register {email, password, display_name?} -> UserOut (SIN token)
 * - POST /v1/auth/token    {email, password}               -> access/refresh
 * - GET  /v1/auth/me                                        -> UserOut
 */

/** Respuesta de `POST /v1/auth/token`. */
export const TokenResponseSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.string(),
  refresh_token: z.string().min(1),
});
export type TokenResponse = z.infer<typeof TokenResponseSchema>;
