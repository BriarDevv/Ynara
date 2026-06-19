import type { IconName } from "@ynara/ui";

/**
 * IA de navegación del panel (blueprint §2.1). A diferencia del web (4 tabs
 * planas), el panel agrupa sus 6 destinos en bloques semánticos con
 * separadores caption uppercase: el grupo sin label es el "Overview" suelto
 * arriba, después Producto, El Moat y Soberanía.
 *
 * Los íconos salen del set propio de marca (`@ynara/ui`, registry validado),
 * nunca emojis ni flechas:
 *  - `foco` (diamante) → Overview: la presencia/foco del panel.
 *  - `red` → Usuarios: el grafo de personas/actividad.
 *  - `adaptacion` → Modos: el carácter adaptativo de Ynara por modo.
 *  - `memoria` → Salud del Moat: las tres capas de memoria (el isotipo de capas).
 *  - `nota` → Audit Log: el registro escrito de operaciones.
 *  - `conexion` → System Health: el enlace con la infra (DB/Redis).
 *  - `dialogo` → Playground: el probe conversacional crudo del modelo.
 */
export type NavItem = {
  href: string;
  label: string;
  icon: IconName;
};

export type NavGroup = {
  /** Caption del grupo (uppercase). Vacío = grupo sin separador (Overview). */
  label: string;
  items: readonly NavItem[];
};

export const NAV_ITEMS: readonly NavGroup[] = [
  { label: "", items: [{ href: "/", label: "Overview", icon: "foco" }] },
  {
    label: "Producto",
    items: [
      { href: "/usuarios", label: "Usuarios", icon: "red" },
      { href: "/modos", label: "Modos", icon: "adaptacion" },
    ],
  },
  {
    label: "El Moat",
    items: [{ href: "/moat", label: "Salud del Moat", icon: "memoria" }],
  },
  {
    label: "Soberanía",
    items: [
      { href: "/audit", label: "Audit Log", icon: "nota" },
      { href: "/sistema", label: "System Health", icon: "conexion" },
      { href: "/playground", label: "Playground", icon: "dialogo" },
    ],
  },
];

/**
 * Un item está activo si la ruta es exactamente su `href` o cuelga de él.
 * Caso especial "/": al ser prefijo de todo, sólo matchea exacto (si no, el
 * Overview quedaría activo en todas las pantallas). Pura para testear sin router.
 */
export function isNavItemActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
