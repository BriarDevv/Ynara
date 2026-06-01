/**
 * Placeholder de las sugerencias mientras carga `GET /v1/suggestions`: dos
 * cards con el pulso suave del sistema, espejando la altura de `SuggestionCard`.
 */
export function SuggestionsSkeleton() {
  return (
    <ul className="flex flex-col gap-3" aria-hidden>
      {[0, 1].map((i) => (
        <li
          key={i}
          className="anim-pulse-soft flex items-stretch gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] p-4"
        >
          <span className="w-1 shrink-0 rounded-full bg-[var(--color-bg)]" />
          <span className="flex flex-1 flex-col gap-2">
            <span className="h-4 w-1/2 rounded-[var(--radius-sm)] bg-[var(--color-bg)]" />
            <span className="h-3 w-3/4 rounded-[var(--radius-sm)] bg-[var(--color-bg)]" />
          </span>
        </li>
      ))}
    </ul>
  );
}
