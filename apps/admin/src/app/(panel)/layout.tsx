import type { ReactNode } from "react";
import { AdminShell } from "@/components/shell/AdminShell";

/**
 * Layout del route group `(panel)`: envuelve las 6 pantallas del panel con el
 * `AdminShell` (sidebar + topbar + atmósfera). Los route groups no agregan
 * segmento de ruta, así que `(panel)/page.tsx` sirve "/" (Overview) y los
 * subsegmentos (`/usuarios`, `/modos`, …) cuelgan del mismo shell.
 *
 * Sin guard de auth en F0: el gate `require_admin` real se cablea en la fase
 * WIRE (token admin en el store + 401 del backend). Acá sólo se monta el chrome.
 */
export default function PanelLayout({ children }: { children: ReactNode }) {
  return <AdminShell>{children}</AdminShell>;
}
