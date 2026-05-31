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
    <div className={cn("flex w-full flex-col gap-2", className)}>
      {label ? (
        <label htmlFor={fieldId} className="text-caption text-[var(--color-ink-muted)]">
          {label}
        </label>
      ) : null}
      <input
        ref={ref}
        id={fieldId}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        className={cn(
          "text-body w-full rounded-[var(--radius-md)] border bg-[var(--color-bg)] px-4 py-3 text-[var(--color-ink)] placeholder:text-[var(--color-ink-muted)] transition-[border-color,box-shadow] duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
          // El borde toma la identidad al foco (complementa el anillo global de :focus-visible, §12).
          invalid
            ? "border-[var(--color-error)]"
            : "border-[var(--color-border)] hover:border-[var(--color-border-strong)] focus:border-[var(--color-accent)]",
        )}
        {...rest}
      />
      {error ? (
        <p id={errorId} role="alert" className="text-body-sm text-[var(--color-error)]">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-body-sm text-[var(--color-ink-muted)]">
          {hint}
        </p>
      ) : null}
    </div>
  );
});
