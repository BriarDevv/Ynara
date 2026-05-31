export type GrainOverlayProps = { className?: string };

/**
 * Capa de grano reutilizable (DESIGN.md §3.6): overlay de ruido monocromo
 * para matar el banding y dar "materia física". Envuelve el utility
 * `.bg-grain` de `globals.css` (pseudo-elemento `::after` con
 * `--texture-grain`, opacity ~0.04, `mix-blend-mode: overlay`) y lo
 * posiciona como capa absoluta que llena su contenedor. Decorativo.
 *
 * **Web-first (deuda de portabilidad RN).** Depende de la clase global
 * `.bg-grain` (pseudo-elemento), que no existe en React Native. Para RN
 * la versión necesita otra estrategia (imagen/SVG de ruido) — TODO al
 * llegar el consumidor mobile.
 */
export function GrainOverlay({ className }: GrainOverlayProps) {
  return (
    <div
      aria-hidden
      className={["bg-grain", className].filter(Boolean).join(" ")}
      // `position: absolute` (inline) pisa el `position: relative` del
      // utility para que el `::after` llene este overlay = el contenedor.
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
    />
  );
}
