import { api } from "../../api";
import { type AuthUser, AuthUserSchema, type TokenResponse, TokenResponseSchema } from "./schemas";

/*
 * Llamadas de auth contra el backend real, compartibles web + mobile (ADR-012).
 * `register`/`login`/`me` son las rutas crudas; `signUp`/`logIn` orquestan el
 * par de llamadas que cada flujo necesita y devuelven una `AuthSession` lista
 * para el draft store del onboarding.
 *
 * Perímetro durante el onboarding: todavía no hay sesión en el user store (el
 * token vive en el draft), así que el cliente NO adjunta el Bearer solo.
 * `register`/`login` son públicos (`skipAuth`); `me` recibe el token explícito.
 */

export type Credentials = { email: string; password: string };

/** Sesión resuelta: lo que el draft store del onboarding necesita para `setAuth`. */
export type AuthSession = { userId: string; token: string };

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

/**
 * `GET /v1/auth/me`. Durante el onboarding pasá el `token` explícito (el user
 * store todavía no tiene sesión); ya logueado, sin args, lo adjunta el cliente.
 */
export async function me(token?: string): Promise<AuthUser> {
  const init = token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;
  const raw = await api.get<unknown>("/v1/auth/me", init);
  return AuthUserSchema.parse(raw);
}

/** Signup: `register` + `token`. Devuelve la sesión lista para el draft. */
export async function signUp(input: Credentials & { displayName?: string }): Promise<AuthSession> {
  const user = await register(input);
  const token = await login({ email: input.email, password: input.password });
  return { userId: user.id, token: token.access_token };
}

/** Login: `token` + `me` (para resolver el `userId`). */
export async function logIn(input: Credentials): Promise<AuthSession> {
  const token = await login(input);
  const user = await me(token.access_token);
  return { userId: user.id, token: token.access_token };
}
