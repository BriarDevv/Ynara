import { useId } from "react";
import { cn } from "@/lib/cn";

type ChipOption<T extends string> = {
  value: T;
  label: string;
};

type Props<T extends string> = {
  label?: string;
  options: readonly ChipOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
};

export function ChipGroup<T extends string>({
  label,
  options,
  value,
  onChange,
  className,
}: Props<T>) {
  const groupId = useId();
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {label ? (
        <span id={`${groupId}-label`} className="text-caption text-[var(--color-ink-muted)]">
          {label}
        </span>
      ) : null}
      <div
        role="radiogroup"
        aria-labelledby={label ? `${groupId}-label` : undefined}
        className="inline-flex w-fit gap-2 rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)] p-1"
      >
        {options.map((opt) => {
          const selected = opt.value === value;
          return (
            // biome-ignore lint/a11y/useSemanticElements: patrón de pill-toggle visual; <input type="radio"> no acepta children con tipografía/spacing/shadow custom. Conserva a11y vía role + aria-checked + radiogroup.
            <button
              key={opt.value}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(opt.value)}
              className={cn(
                "text-button rounded-[var(--radius-pill)] px-4 py-2 transition-colors duration-[var(--duration-base)] ease-[var(--ease-out-soft)]",
                selected
                  ? "bg-[var(--color-bg)] text-[var(--color-ink)] shadow-soft"
                  : "text-[var(--color-ink-soft)] hover:text-[var(--color-ink)]",
              )}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
