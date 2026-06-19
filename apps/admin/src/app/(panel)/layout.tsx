import type { ReactNode } from "react";
import { AdminShell } from "@/components/shell/AdminShell";
import { AuthGuard } from "@/components/shell/AuthGuard";

/**
 * Layout del route group `(panel)`: envuelve las 6 pantallas del panel con el
 * `AdminShell` (sidebar + topbar + atmósfera). Los route groups no agregan
 * segmento de ruta, así que `(panel)/page.tsx` sirve "/" (Overview) y los
 * subsegmentos (`/usuarios`, `/modos`, …) cuelgan del mismo shell.
 *
 * Guard de sesión (fase WIRE): `AuthGuard` rebota a `/login` si no hay token
 * admin (SSR-safe, post-mount). El gate `require_admin` del backend (401 en
 * `/v1/admin/*`) lo maneja el `QueryCache` de `providers.tsx`, que resetea el
 * store y deja que este guard redirija.
 */
export default function PanelLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <AdminShell>{children}</AdminShell>
    </AuthGuard>
  );
}
