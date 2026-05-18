import { forwardRef, type TextareaHTMLAttributes, useId } from "react";
import { cn } from "@/lib/cn";

type Props = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "className"> & {
  label?: string;
  hint?: string;
  error?: string;
  className?: string;
};

export const Textarea = forwardRef<HTMLTextAreaElement, Props>(function Textarea(
  { label, hint, error, id, className, rows = 4, ...rest },
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
      <textarea
        ref={ref}
        id={fieldId}
        rows={rows}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        className={cn(
          "text-body w-full resize-y rounded-[var(--radius-md)] border bg-[var(--color-bg)] px-4 py-3 text-[var(--color-ink)] placeholder:text-[var(--color-ink-muted)] transition-[border-color,box-shadow] duration-[var(--duration-base)] ease-[var(--ease-out-soft)]",
          invalid
            ? "border-[#c0392b]"
            : "border-[var(--color-border)] hover:border-[var(--color-border-strong)]",
        )}
        {...rest}
      />
      {error ? (
        <p id={errorId} role="alert" className="text-body-sm text-[#c0392b]">
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
