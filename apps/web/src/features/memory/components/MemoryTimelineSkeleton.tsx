/**
 * Skeleton del timeline mientras carga (DESIGN §8.2: skeleton, no spinner).
 * Filas-fantasma con un pulso suave; `aria-hidden` + un status para el lector
 * de pantalla. Cantidad fija de filas para no saltar el layout.
 */
export function MemoryTimelineSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div>
      <span className="sr-only" role="status">
        Cargando tu memoria…
      </span>
      <ul aria-hidden className="flex flex-col gap-3">
        {Array.from({ length: rows }, (_, i) => (
          <li
            // biome-ignore lint/suspicious/noArrayIndexKey: filas de skeleton estáticas, sin identidad propia ni reordenamiento.
            key={i}
            className="anim-pulse-soft flex items-start gap-4 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)] p-4"
          >
            <span className="h-9 w-9 shrink-0 rounded-[var(--radius-md)] bg-[var(--color-bg-soft)]" />
            <span className="flex min-w-0 flex-1 flex-col gap-2 pt-1">
              <span className="h-2.5 w-16 rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)]" />
              <span className="h-3.5 w-full rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)]" />
              <span className="h-3.5 w-2/3 rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)]" />
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
