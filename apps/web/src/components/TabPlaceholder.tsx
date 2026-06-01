import { Icon, type IconName } from "@ynara/ui";

/**
 * Placeholder editorial para las tabs/sub-vistas que todavía no se
 * construyeron (build-plan Fase A/A2). Centrado, con un ícono del set propio
 * (DESIGN.md §9) + título + nota de qué viene. No usa el `EmptyStateCard`
 * (borde punteado = "lista vacía"); acá la vista entera está por venir.
 */
export function TabPlaceholder({
  icon,
  title,
  hint,
}: {
  icon: IconName;
  title: string;
  hint: string;
}) {
  return (
    <div className="flex min-h-full flex-1 flex-col items-center justify-center gap-4 px-6 py-16 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--color-bg-soft)] text-[var(--color-ink-soft)]">
        <Icon name={icon} size={28} />
      </span>
      <h1 className="text-title text-[var(--color-ink)]">{title}</h1>
      <p className="max-w-[40ch] text-body text-[var(--color-ink-soft)]">{hint}</p>
    </div>
  );
}
