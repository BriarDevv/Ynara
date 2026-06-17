import { Icon } from "@ynara/ui";

type Props = {
  onOpen: () => void;
};

/**
 * CTA "Check-in matinal" (wireframe 14): card full-width que invita a hacer
 * el check-in de la mañana. Paralelo a RecapCta pero para el inicio del día.
 */
export function CheckinCta({ onOpen }: Props) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="group flex w-full items-center gap-4 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-glass)] p-4 text-left shadow-soft backdrop-blur-sm transition-[border-color,background-color] duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-soft)]"
    >
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-caption text-[var(--color-ink-soft)]">Buenos días</span>
        <span className="text-body font-medium text-[var(--color-ink)]">¿Cómo arrancás hoy?</span>
      </span>
      <span
        aria-hidden
        className="shrink-0 text-[var(--color-ink-soft)] transition-opacity duration-[var(--duration-fast)] group-hover:text-[var(--color-ink)]"
      >
        <Icon name="chevron" size={20} className="-rotate-90" />
      </span>
    </button>
  );
}
