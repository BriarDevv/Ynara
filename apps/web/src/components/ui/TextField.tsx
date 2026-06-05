import { forwardRef, type InputHTMLAttributes, useId } from "react";
import { cn } from "@/lib/cn";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "className"> & {
  label?: string;
  hint?: string;
  /** Mensaje de error inline. Si está presente, marca el campo como inválido. */
  error?: string;
  className?: string;
};

export const TextField = forwardRef<HTMLInputElement, Props>(function TextField(
  { label, hint, error, id, className, ...rest },
  ref,
) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const hintId = hint ? `${fieldId}-hint` : undefined;
  const errorId = error ? `${fieldId}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  const invalid = Boolean(error);

  return (
    <div className={cn("flex w-full flex-col gap-1.5", className)}>
      {label ? (
        /*
         * Label en text-caption + ink-soft (no muted): más presencia que
         * el muted anterior; sigue jerárquicamente por debajo del input
         * pero ya no se "pierde" sobre canvas ivory.
         */
        <label htmlFor={fieldId} className="text-caption text-[var(--color-ink-soft)]">
          {label}
        </label>
      ) : null}
      <input
        ref={ref}
        id={fieldId}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        /*
         * - py-3.5: ~52px alto efectivo; sensación premium sin pasar al
         *   "form gigante" mobile.
         * - border default → border-strong en hover; el focus-visible
         *   global aplica el ring de accent encima, no duplicamos foco.
         */
        className={cn(
          "text-body w-full rounded-[var(--radius-md)] border bg-[var(--color-bg)] px-4 py-3.5 text-[var(--color-ink)] placeholder:text-[var(--color-ink-muted)] transition-[border-color,background-color] duration-[var(--duration-base)] ease-[var(--ease-out-soft)]",
          invalid
            ? "border-[var(--color-error)]"
            : "border-[var(--color-border)] hover:border-[var(--color-border-strong)]",
        )}
        {...rest}
      />
      {error ? (
        <p id={errorId} role="alert" className="text-body-sm text-[var(--color-error)]">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-body-sm text-[var(--color-ink-soft)]">
          {hint}
        </p>
      ) : null}
    </div>
  );
});
