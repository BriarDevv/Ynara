import { type UserOut, UserOutSchema } from "@ynara/shared-schemas";
import { api } from "../../api";
import { type AuthUser, AuthUserSchema, type TokenResponse, TokenResponseSchema } from "./schemas";

/*
 * Llamadas de auth contra el backend real, compartibles web + mobile (ADR-012).
 * `register`/`login` son las rutas crudas; `signUp`/`logIn` orquestan el par de
 * llamadas que cada flujo necesita. `signUp` devuelve una `AuthSession` para el
 * draft del onboarding; `logIn` devuelve un `LoginResult` (sesión + `UserOut`).
 *
 * Perímetro durante el onboarding: todavía no hay sesión en el user store (el
 * token vive en el draft), así que el cliente NO adjunta el Bearer solo.
 * `register`/`login` son públicos (`skipAuth`); `logIn` adjunta el Bearer
 * explícito a su `GET /v1/auth/me` (el token recién emitido).
 */

export type Credentials = { email: string; password: string };

/** Sesión resuelta: lo que el draft store del onboarding necesita para `setAuth`. */
export type AuthSession = { userId: string; token: string };

/**
 * Resultado del login: la sesión + el **perfil completo** (`UserOut`) del usuario.
 * `logIn` ya pega a `/v1/auth/me`, así que devolvemos ese perfil para que el
 * caller pueda recuperar el estado de un usuario que YA onboardeó (G3b: login en
 * dispositivo nuevo → hidratar y saltar el onboarding) sin un segundo fetch.
 */
export type LoginResult = AuthSession & { user: UserOut };

/** `POST /v1/auth/register` — crea el user. No devuelve token (se pide aparte). */
export async function register(input: Credentials & { displayName?: string }): Promise<AuthUser> {
  const body: Record<string, unknown> = { email: input.email, password: input.password };
  if (input.displayName) body.display_name = input.displayName;
  const raw = await api.post<unknown>("/v1/auth/register", body, { skipAuth: true });
  return AuthUserSchema.parse(raw);
}

/** `POST /v1/auth/token` — login con credenciales: access + refresh. */
export async function login(input: Credentials): Promise<TokenResponse> {
  const raw = await api.post<unknown>("/v1/auth/token", input, { skipAuth: true });
  return TokenResponseSchema.parse(raw);
}

/** Signup: `register` + `token`. Devuelve la sesión lista para el draft. */
export async function signUp(input: Credentials & { displayName?: string }): Promise<AuthSession> {
  const user = await register(input);
  const token = await login({ email: input.email, password: input.password });
  return { userId: user.id, token: token.access_token };
}

/**
 * Login: `token` + `GET /v1/auth/me`. Devuelve la sesión + el `UserOut` completo.
 *
 * Parsea el `me` con `UserOutSchema` (incluye `preferences`/`retention`), no con
 * `AuthUserSchema` (subset): G3b necesita el perfil completo para recuperar el
 * estado del usuario en un dispositivo nuevo. El Bearer va explícito porque el
 * user store todavía no tiene sesión durante el onboarding.
 */
export async function logIn(input: Credentials): Promise<LoginResult> {
  const token = await login(input);
  const raw = await api.get<unknown>("/v1/auth/me", {
    headers: { Authorization: `Bearer ${token.access_token}` },
  });
  const user = UserOutSchema.parse(raw);
  return { userId: user.id, token: token.access_token, user };
}

/**
 * `POST /v1/auth/logout` — revoca la sesión actual server-side.
 *
 * Con el Bearer del access token el backend revoca la FAMILIA entera (vía el claim
 * `sid`): el access actual y cualquier access/refresh hermano dejan de servir
 * aunque no hayan expirado. NO se manda el refresh token en el body: la
 * family-revocation por `sid` ya lo cubre, así que el cliente no necesita persistir
 * el refresh (menos superficie de XSS).
 *
 * Best-effort por diseño: el caller la dispara fire-and-forget y limpia el estado
 * local igual si esto falla (sin revocación, el token expira solo). El token va
 * explícito porque el caller suele resetear el user store en el mismo tick.
 */
export async function logOut(token: string): Promise<void> {
  await api.post("/v1/auth/logout", {}, { headers: { Authorization: `Bearer ${token}` } });
}
