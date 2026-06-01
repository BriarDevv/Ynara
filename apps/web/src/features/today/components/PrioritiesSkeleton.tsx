/**
 * Placeholder de las prioridades mientras carga `GET /v1/tasks`: tres filas con
 * el pulso suave del sistema (`.anim-pulse-soft`), espejando la altura de
 * `PriorityRow` para evitar el salto de layout al llegar los datos.
 */
export function PrioritiesSkeleton() {
  return (
    <ul className="flex flex-col gap-3" aria-hidden>
      {[0, 1, 2].map((i) => (
        <li
          key={i}
          className="anim-pulse-soft flex items-start gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)] p-4"
        >
          <span className="mt-0.5 h-6 w-6 shrink-0 rounded-full bg-[var(--color-bg-soft)]" />
          <span className="flex flex-1 flex-col gap-2">
            <span className="h-4 w-3/5 rounded-[var(--radius-sm)] bg-[var(--color-bg-soft)]" />
            <span className="h-3 w-2/5 rounded-[var(--radius-sm)] bg-[var(--color-bg-soft)]" />
          </span>
        </li>
      ))}
    </ul>
  );
}
