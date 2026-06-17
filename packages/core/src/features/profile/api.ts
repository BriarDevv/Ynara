"use client";

import { useMutation } from "@tanstack/react-query";
import {
  type UserOut,
  UserOutSchema,
  type UserUpdate,
  UserUpdateSchema,
} from "@ynara/shared-schemas";
import { api } from "../../api";

/**
 * Hooks de **perfil** (tab Tú), compartidos web + mobile (ADR-012). El perfil
 * persistente del cliente vive en el user store de cada app (zustand); este hook
 * cablea el endpoint real `PATCH /v1/users/me`. La vista reconcilia el store con
 * el `UserOut` devuelto.
 */

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
