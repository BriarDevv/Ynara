import type { IconName } from "@ynara/ui";

/**
 * Las 4 tabs del app shell (FRONTEND-APP-BUILD-PLAN §3.1): `Hoy / Chat /
 * Agenda / Tú`. Misma config para el bottom-tab bar mobile y el sidebar
 * desktop — el chrome cambia por breakpoint, los destinos no.
 *
 * Los íconos salen del set propio (`@ynara/ui`, DESIGN.md §9), nunca emojis
 * ni flechas: `foco` es el diamante (presencia/foco del día), `dialogo` la
 * conversación, `recordatorio` el reloj de la agenda y `adaptacion` el
 * carácter adaptativo del perfil.
 */
export type NavItem = {
  id: string;
  href: string;
  label: string;
  icon: IconName;
};

export const NAV_ITEMS: readonly NavItem[] = [
  { id: "hoy", href: "/hoy", label: "Hoy", icon: "foco" },
  { id: "chat", href: "/chat", label: "Chat", icon: "dialogo" },
  { id: "agenda", href: "/agenda", label: "Agenda", icon: "recordatorio" },
  { id: "tu", href: "/tu", label: "Tú", icon: "adaptacion" },
];

/**
 * Una tab está activa si la ruta es exactamente su `href` o cuelga de él
 * (`/chat/123` activa la tab Chat). Pura para poder testearla sin router.
 *
 * Nota: hoy la conversación `/chat/[sessionId]` vive fuera del route group
 * `(app)` (sin shell); la Fase A2 la mueve adentro y ahí el match por prefijo
 * de la tab Chat cobra efecto visual.
 */
export function isNavItemActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
