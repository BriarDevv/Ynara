"use client";

import { type KeyboardEvent, useId, useRef } from "react";
import { cn } from "@/lib/cn";

type ChipOption<T extends string> = {
  value: T;
  label: string;
};

type Props<T extends string> = {
  label?: string;
  /** Nombre accesible del radiogroup cuando no hay `label` visible (ej. el
   * switcher de vistas de la Agenda, que va al lado del h1 sin label propio). */
  ariaLabel?: string;
  options: readonly ChipOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
};

/**
 * Pill-toggle group con semántica de radiogroup.
 *
 * Implementa el patrón WAI-ARIA Radio Group:
 *  - `tabIndex={selected ? 0 : -1}`: el grupo entra una sola vez con Tab.
 *  - ArrowLeft/Right (y Home/End): mueven la selección dentro del grupo.
 *
 * Reflow (M4): la barra es `w-fit max-w-full overflow-x-auto`, así que hugea su
 * contenido pero nunca excede al padre; cuando los chips no entran (mobile)
 * scrollea en X en vez de clippear. Los chips son `shrink-0` y el wrapper
 * externo `min-w-0` para achicarse en filas flex. La affordance es el peek del
 * chip cortado + el scrollbar nativo (no hay utility `scrollbar-none` en el
 * repo); el `focus()` de la navegación por flechas auto-scrollea el chip a la
 * vista. El overflow clippea el `box-shadow` del chip seleccionado en los
 * lados, pero es imperceptible por el alpha bajo de `--shadow-soft` + el `p-1`.
 *
 * Referencia: https://www.w3.org/WAI/ARIA/apd/patterns/radio/
 */
export function ChipGroup<T extends string>({
  label,
  ariaLabel,
  options,
  value,
  onChange,
  className,
}: Props<T>) {
  const groupId = useId();
  const buttonsRef = useRef<Map<T, HTMLButtonElement>>(new Map());

  const focusValue = (next: T) => {
    onChange(next);
    requestAnimationFrame(() => buttonsRef.current.get(next)?.focus());
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (options.length === 0) return;
    const currentIndex = options.findIndex((opt) => opt.value === value);
    if (currentIndex < 0) return;

    const moveTo = (index: number) => {
      const target = options[((index % options.length) + options.length) % options.length];
      if (target) focusValue(target.value);
    };

    switch (event.key) {
      case "ArrowRight":
      case "ArrowDown":
        event.preventDefault();
        moveTo(currentIndex + 1);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        event.preventDefault();
        moveTo(currentIndex - 1);
        break;
      case "Home":
        event.preventDefault();
        moveTo(0);
        break;
      case "End":
        event.preventDefault();
        moveTo(options.length - 1);
        break;
    }
  };

  return (
    <div className={cn("flex min-w-0 flex-col gap-3", className)}>
      {label ? (
        <span id={`${groupId}-label`} className="text-caption text-[var(--color-ink-soft)]">
          {label}
        </span>
      ) : null}
      <div
        role="radiogroup"
        aria-labelledby={label ? `${groupId}-label` : undefined}
        aria-label={label ? undefined : ariaLabel}
        onKeyDown={handleKeyDown}
        // Reflow horizontal (M4) — ver JSDoc del componente.
        className="inline-flex w-fit max-w-full gap-2 overflow-x-auto rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)] p-1"
      >
        {options.map((opt) => {
          const selected = opt.value === value;
          return (
            // biome-ignore lint/a11y/useSemanticElements: patrón de pill-toggle visual; <input type="radio"> no acepta children con tipografía/spacing/shadow custom. Conserva a11y vía role + aria-checked + radiogroup + keyboard nav (ArrowLeft/Right/Home/End).
            <button
              key={opt.value}
              ref={(el) => {
                if (el) buttonsRef.current.set(opt.value, el);
                else buttonsRef.current.delete(opt.value);
              }}
              type="button"
              role="radio"
              aria-checked={selected}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(opt.value)}
              className={cn(
                "text-button shrink-0 rounded-[var(--radius-pill)] px-4 py-2 transition-colors duration-[var(--duration-base)] ease-[var(--ease-out-soft)]",
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
