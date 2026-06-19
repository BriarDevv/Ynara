"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";
import { useAdminStore } from "@/stores/admin";

/**
 * Guard de sesión del route group `(panel)`: si no hay token admin, rebota a
 * `/login`. El wire del gate `require_admin` real lo cierra el backend (401 en
 * `/v1/admin/*` → `providers.tsx` resetea el store); este guard solo cubre la
 * ausencia de token (no logueado o sesión reseteada).
 *
 * **SSR-safe**: el token vive en Zustand persist (localStorage), que NO existe
 * en el server ni en el primer paint pre-hidratación. Por eso el chequeo corre
 * en un `useEffect` (post-mount) y hasta entonces no se renderiza el panel: se
 * evita el flash de contenido protegido y el mismatch de hidratación. El
 * `replace` (no `push`) no deja el panel en el historial del navegador.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const token = useAdminStore((s) => s.token);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (token === null) {
      router.replace("/login");
      return;
    }
    setChecked(true);
  }, [token, router]);

  // Sin token o todavía sin verificar (pre-mount): no pintar el panel.
  if (!checked || token === null) return null;

  return <>{children}</>;
}
