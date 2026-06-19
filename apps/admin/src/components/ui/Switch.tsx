"use client";

import { useId } from "react";
import { cn } from "@/lib/cn";

type Props = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Label visible a la izquierda del track. */
  label: string;
  /** Hint opcional bajo el label (text-caption ink-soft). */
  hint?: string;
  disabled?: boolean;
  className?: string;
};

/**
 * Toggle a11y con semántica de switch (WAI-ARIA Switch pattern).
 *
 * `role="switch"` + `aria-checked` + label asociado (`aria-labelledby`); Space y
 * Enter (nativos del `<button>`) alternan el estado. "On" usa el azul plano de
 * marca (`--color-blue-flat`) —el panel no tiene token de success ni gradiente—,
 * "off" cae a `--color-border-strong`. El thumb desliza con la transición global
 * (respeta `prefers-reduced-motion`). Foco visible vía el `focus-visible` ring
 * de tokens.
 *
 * Referencia: https://www.w3.org/WAI/ARIA/apg/patterns/switch/
 */
export function Switch({ checked, onChange, label, hint, disabled = false, className }: Props) {
  const labelId = useId();
  const hintId = useId();

  return (
    <div className={cn("flex items-center justify-between gap-4", className)}>
      <div className="flex min-w-0 flex-col gap-0.5">
        <span id={labelId} className="text-body-sm text-[var(--color-ink)]">
          {label}
        </span>
        {hint ? (
          <span id={hintId} className="text-caption tabular-nums text-[var(--color-ink-soft)]">
            {hint}
          </span>
        ) : null}
      </div>

      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={labelId}
        aria-describedby={hint ? hintId : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-6 w-11 shrink-0 items-center rounded-[var(--radius-pill)] transition-colors duration-[var(--duration-base)] ease-[var(--ease-out-soft)] disabled:cursor-not-allowed disabled:opacity-50",
          checked ? "bg-[var(--color-blue-flat)]" : "bg-[var(--color-border-strong)]",
        )}
      >
        <span
          aria-hidden
          className={cn(
            "inline-block size-5 rounded-[var(--radius-pill)] bg-[var(--color-bg)] shadow-soft transition-transform duration-[var(--duration-base)] ease-[var(--ease-out-soft)]",
            checked ? "translate-x-[22px]" : "translate-x-0.5",
          )}
        />
      </button>
    </div>
  );
}
