"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { api } from "@/lib/api";
import { useAdminStore } from "@/stores/admin";

/**
 * Hook de logout admin (wire del contrato REAL `/v1/auth/logout`).
 *
 * `POST /v1/auth/logout` es **best-effort**: avisamos al backend para que
 * invalide el refresh token, pero la sesión local se baja pase lo que pase
 * (red caída, 401 por token ya vencido, etc.). El orden importa:
 *  1. POST logout con el Bearer actual (si falla, lo tragamos).
 *  2. `reset()` del admin store → el guard de `(panel)/layout.tsx` reacciona.
 *  3. Limpiar la cache de TanStack Query (datos del operador anterior).
 *  4. `router.replace("/login")` → la pantalla pública (no deja "atrás").
 *
 * `replace` (no `push`): no querés que el back del navegador vuelva al panel
 * ya deslogueado.
 */
export function useLogout(): { logout: () => Promise<void> } {
  const router = useRouter();
  const queryClient = useQueryClient();

  const logout = useCallback(async () => {
    try {
      await api.post<unknown>("/v1/auth/logout", {});
    } catch {
      // Best-effort: la sesión local se baja igual.
    }
    useAdminStore.getState().reset();
    queryClient.clear();
    router.replace("/login");
  }, [router, queryClient]);

  return { logout };
}
