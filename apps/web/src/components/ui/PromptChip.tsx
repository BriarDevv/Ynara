import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Props = {
  label: string;
  /** Handler obligatorio: un PromptChip sin acción es un chip muerto. */
  onClick: () => void;
  /** Ícono opcional a la izquierda (set propio de @ynara/ui). */
  leading?: ReactNode;
  disabled?: boolean;
  className?: string;
};

/**
 * Chip de prompt accionable para empty states de chat (DESIGN.md §11): el
 * usuario lo toca para arrancar una conversación con un disparador sugerido.
 * Pill de tamaño chico → el scale(1.02) de §8.2 es seguro (no desborda).
 */
export function PromptChip({ label, onClick, leading, disabled = false, className }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "inline-flex items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--color-border)] bg-[var(--color-bg)] px-4 py-2 text-body-sm text-[var(--color-ink-soft)] transition-[transform,box-shadow,border-color,color] duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:scale-[1.02] hover:border-[var(--color-border-strong)] hover:text-[var(--color-ink)] hover:shadow-soft active:scale-[0.98] active:duration-[var(--duration-instant)] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100",
        className,
      )}
    >
      {leading ? (
        <span aria-hidden className="shrink-0 text-[var(--color-memory)]">
          {leading}
        </span>
      ) : null}
      <span>{label}</span>
    </button>
  );
}
