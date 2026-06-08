import type { ReactNode } from "react";

/**
 * Template del grupo `(app)`: a diferencia de un `layout`, se **re-monta en
 * cada navegación**, así que es el lugar canónico del App Router para la
 * transición de pantalla (DESIGN.md §8.3 "cambio de pantalla"). Cada vista
 * entra con un crossfade de opacidad (`anim-screen-in`, `--duration-screen`
 * 350ms), neutralizado por la cascada global de reduced-motion (globals.css:
 * bajo reduce la animación corre en ~0ms con `both`, así el contenido queda
 * visible sin flash).
 *
 * Opacidad pura (sin `transform`): un transform residual haría de este wrapper
 * un containing block de los overlays `position: fixed` que cuelgan adentro
 * (el Toast de Hoy), desanclándolos del viewport. `opacity: 1` es inerte.
 *
 * Layout: `flex flex-1 flex-col` para conservar el contrato del shell — el
 * `<main>` es de altura fija con scroll interno, y este wrapper (su único hijo,
 * y por ende el `content` de Lenis en #7) debe tener altura definida para que
 * las vistas `h-full` (Chat) calcen y las `min-h-full` (Hoy/Memoria/Buscar)
 * crezcan y scrolleen.
 *
 * El crossfade verdadero entre rutas (shared-element, la saliente desvaneciendo
 * mientras entra la nueva) necesita el componente `<ViewTransition>` de React,
 * que no está en react 19.0.0 (solo canary) — queda diferido. Esto entrega la
 * entrada de pantalla, robusta y sin flags experimentales.
 */
export default function AppTemplate({ children }: { children: ReactNode }) {
  return <div className="flex flex-1 flex-col anim-screen-in">{children}</div>;
}
