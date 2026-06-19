/**
 * Fallback de carga del grupo `(panel)` (blueprint §5). Skeleton genérico de
 * pantalla: una banda de header + una grilla de tarjetas placeholder con
 * shimmer suave. Es el boundary de Suspense de todos los segmentos anidados, así
 * que cubre las 6 pantallas. Vive dentro del `<main>` del shell (no el viewport
 * entero) y entra con el mismo fade del template que lo envuelve.
 *
 * `role="status"` para que el lector de pantalla anuncie la carga sin robar el
 * foco. El shimmer es `anim-pulse-soft` (opacidad pura, GPU-safe, se neutraliza
 * bajo reduced-motion).
 */
export default function PanelLoading() {
  return (
    <div role="status" aria-label="Cargando pantalla" className="flex flex-col gap-8">
      {/* Header skeleton. */}
      <div className="flex flex-col gap-3">
        <div className="anim-pulse-soft h-3 w-24 rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)]" />
        <div className="anim-pulse-soft h-10 w-72 rounded-[var(--radius-md)] bg-[var(--color-bg-soft)]" />
      </div>
      {/* Grilla de tarjetas placeholder. */}
      <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="anim-pulse-soft h-32 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]"
          />
        ))}
      </div>
      <div className="anim-pulse-soft h-64 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]" />
    </div>
  );
}
