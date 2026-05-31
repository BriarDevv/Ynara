import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Props = {
  title: ReactNode;
  hint?: ReactNode;
  selected?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  /** Slot a la izquierda (icono, ModeChip, etc.) */
  leading?: ReactNode;
  className?: string;
};

export function OptionCard({
  title,
  hint,
  selected = false,
  disabled = false,
  onClick,
  leading,
  className,
}: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={selected}
      className={cn(
        // Target full-width: el feedback de hover es elevación + borde (sin scale,
        // que en full-width podría desbordar), a 150ms (§8.2 "+ leve elevación").
        "relative w-full rounded-[var(--radius-md)] border p-6 text-left transition-[box-shadow,background-color,border-color] duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] disabled:cursor-not-allowed disabled:opacity-50",
        selected
          ? "border-[var(--color-ink)] bg-[var(--color-ink)] text-[var(--color-on-dark)]"
          : "border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-ink)] hover:border-[var(--color-border-strong)] hover:shadow-soft",
        className,
      )}
    >
      {/* Hairline gradient en selected — devuelve calidez al ink plano */}
      {selected ? (
        <span
          aria-hidden
          className="bg-gradient-blue-relief pointer-events-none absolute inset-0 rounded-[var(--radius-md)] opacity-30"
          style={{
            mask: "linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)",
            maskComposite: "exclude",
            WebkitMask: "linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)",
            WebkitMaskComposite: "xor",
            padding: "1px",
          }}
        />
      ) : null}
      <div className="relative flex items-start gap-4">
        {leading ? <span className="shrink-0">{leading}</span> : null}
        <span className="flex flex-col gap-1">
          <span className="text-subtitle">{title}</span>
          {hint ? (
            <span
              className={cn(
                "text-body-sm italic",
                selected ? "text-[rgb(255_255_255_/_0.72)]" : "text-[var(--color-ink-soft)]",
              )}
            >
              {hint}
            </span>
          ) : null}
        </span>
      </div>
    </button>
  );
}
