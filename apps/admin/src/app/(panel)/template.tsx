import type { ReactNode } from "react";

/**
 * Template del grupo `(panel)`: a diferencia de un `layout`, se re-monta en cada
 * navegación, así que es el lugar canónico para la transición de pantalla
 * (blueprint §5 "transición de pantalla"). Cada pantalla entra con un crossfade
 * de opacidad (`anim-screen-in`, `--duration-screen` 350ms), neutralizado por la
 * cascada de reduced-motion de globals.css (bajo reduce corre en ~0ms, el
 * contenido queda visible sin flash).
 *
 * Opacidad pura, sin `transform`: un transform residual convertiría este wrapper
 * en containing block de los overlays `position: fixed` que cuelgan adentro
 * (tooltips, toasts), desanclándolos del viewport.
 *
 * El crossfade real entre rutas (View Transitions root, `::view-transition-*`)
 * vive en globals.css; este wrapper entrega la entrada de pantalla robusta sin
 * depender del componente `<ViewTransition>` de React (solo canary en 19.0.0).
 */
export default function PanelTemplate({ children }: { children: ReactNode }) {
  return <div className="anim-screen-in flex flex-1 flex-col">{children}</div>;
}
