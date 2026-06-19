"use client";

import { useMutation } from "@tanstack/react-query";
import { ApiError, api } from "@/lib/api";
import { useAdminStore } from "@/stores/admin";
import { LoginRequest, type LoginRequestT, MeOut, type MeOutT, TokenOut } from "../schemas";

/**
 * Hook de login admin (wire del contrato REAL `/v1/auth/*`).
 *
 * Flujo en dos pasos, encadenado dentro del `mutationFn` para que un fallo de
 * cualquiera de los dos caiga en `onError` con el mensaje correcto:
 *  1. `POST /v1/auth/token` **sin token** (`skipAuth`): el endpoint es público.
 *     Devuelve `TokenOut`; guardamos `access_token` en el admin store
 *     (`setToken`) para que el cliente HTTP lo adjunte al paso 2.
 *  2. `GET /v1/auth/me` (ya con Bearer del paso 1): trae la identidad del
 *     operador. Con eso completamos la sesión (`setAuth`: adminId + token +
 *     display_name) que pinta el Topbar.
 *
 * El gate `is_admin` NO se chequea acá (el `UserOut` no lo expone): si el user
 * no es admin, los `/v1/admin/*` devuelven 401 y el handler global de
 * `providers.tsx` resetea la sesión. Login en sí solo valida credenciales.
 *
 * Mensajes de error mapeados del status del backend:
 *  - 401 → "Credenciales inválidas" (detail del backend: "credenciales invalidas").
 *  - 429 → "Demasiados intentos, probá más tarde" (lockout con Retry-After).
 *  - resto → mensaje genérico de reintento.
 */

/** Texto del error de login a partir del `ApiError` (o un fallback genérico). */
export function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Credenciales inválidas";
    if (error.status === 429) return "Demasiados intentos, probá más tarde";
  }
  return "No pudimos iniciar sesión. Probá de nuevo en un momento.";
}

export function useLogin() {
  return useMutation<MeOutT, unknown, LoginRequestT>({
    mutationFn: async (values) => {
      const credentials = LoginRequest.parse(values);

      // Paso 1: token público (sin Bearer). Persistimos el access_token YA, así
      // el cliente HTTP lo adjunta solo al `/v1/auth/me` del paso 2.
      const token = TokenOut.parse(
        await api.post<unknown>("/v1/auth/token", credentials, { skipAuth: true }),
      );
      useAdminStore.getState().setToken(token.access_token);

      // Paso 2: identidad del operador (con el Bearer recién guardado).
      const me = MeOut.parse(await api.get<unknown>("/v1/auth/me"));
      useAdminStore.getState().setAuth({
        adminId: me.id,
        token: token.access_token,
        displayName: me.display_name,
      });
      return me;
    },
    onError: () => {
      // Si el paso 1 guardó un token pero el paso 2 falló, dejamos la sesión
      // limpia: no querés un token a medias en el store.
      useAdminStore.getState().reset();
    },
  });
}
