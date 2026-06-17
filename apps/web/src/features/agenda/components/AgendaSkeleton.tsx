/**
 * Placeholder de la Agenda mientras carga `GET /v1/events`: tres bloques con el
 * pulso suave del sistema (`.anim-pulse-soft`), espejando la silueta de una
 * fila de evento (spine + rango + título) para evitar el salto de layout.
 */
export function AgendaSkeleton() {
  return (
    <ul className="flex flex-col gap-3" aria-hidden>
      {[0, 1, 2].map((i) => (
        <li
          key={i}
          className="anim-pulse-soft flex gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)] p-3.5"
        >
          <span className="w-1 shrink-0 self-stretch rounded-full bg-[var(--color-bg-soft)]" />
          <span className="flex flex-1 flex-col gap-2">
            <span className="h-3 w-1/4 rounded-[var(--radius-sm)] bg-[var(--color-bg-soft)]" />
            <span className="h-4 w-3/5 rounded-[var(--radius-sm)] bg-[var(--color-bg-soft)]" />
          </span>
        </li>
      ))}
    </ul>
  );
}
