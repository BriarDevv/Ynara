"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  type UserOut,
  UserOutSchema,
  type UserUpdate,
  UserUpdateSchema,
} from "@ynara/shared-schemas";
import { api } from "../../api";
import { qk } from "../../query-keys";

/**
 * Hooks de **perfil** (tab Tú), compartidos web + mobile (ADR-012). El perfil
 * persistente del cliente vive en el user store de cada app (zustand); estos
 * hooks cablean los endpoints reales `GET /v1/auth/me` (lectura) y
 * `PATCH /v1/users/me` (update). La vista reconcilia el store con el `UserOut`.
 */

/**
 * Query del perfil propio (`GET /v1/auth/me`) → `UserOut` (incluye
 * `preferences` + `retention_sensitive_days` reales). Fuente para hidratar la tab
 * Tú (G3): chau retención clavada en 365. `enabled` lo controla el caller según
 * su estado de sesión (sin token el endpoint da 401, no tiene sentido pedirlo).
 * `staleTime` generoso: el perfil cambia poco; tras un `PATCH` el caller invalida
 * `qk.profile.me()` para refrescar.
 */
export function useMe(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: qk.profile.me(),
    queryFn: async (): Promise<UserOut> =>
      UserOutSchema.parse(await api.get<unknown>("/v1/auth/me")),
    enabled: options?.enabled ?? true,
    staleTime: 5 * 60_000,
  });
}

/**
 * Update parcial del perfil (`PATCH /v1/users/me`). Valida el body con Zod antes
 * de salir (display_name del onboarding, retention 30..365). Es una mutation sin
 * cache propia: no hay query "me" en core (el estado vive en el store de la app),
 * así que el caller usa el `UserOut` devuelto para actualizar su store.
 */
export function useUpdateMe() {
  return useMutation({
    mutationFn: async (update: UserUpdate): Promise<UserOut> => {
      const body = UserUpdateSchema.parse(update);
      const raw = await api.patch<unknown>("/v1/users/me", body);
      return UserOutSchema.parse(raw);
    },
  });
}

/** Re-exporta los tipos del dominio para los componentes. */
export type { UserOut, UserUpdate };
