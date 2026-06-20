import { ApiError } from "@ynara/core/api";

export type AuthMode = "signup" | "login";

/**
 * Mapea un error de auth a un mensaje accionable en español. Compartido por el
 * login de la bienvenida y el signup del onboarding. Puro (importa `ApiError` de
 * `@ynara/core/api`, no de `@/lib/api`) para no arrastrar side-effects al test.
 */
export function authErrorMessage(error: unknown, mode: AuthMode): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Email o contraseña incorrectos.";
    if (error.status === 409 || error.status === 400) {
      return mode === "signup"
        ? "Ese email ya tiene una cuenta. Iniciá sesión."
        : "No pudimos validar tus datos.";
    }
    if (error.status === 422) return "Revisá el email y la contraseña.";
  }
  return "Algo no anduvo. Probá de nuevo en un momento.";
}
