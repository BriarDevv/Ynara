import { useId } from "react";
import { cn } from "@/lib/cn";

type Props = {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
};

export function Toggle({ label, hint, checked, onChange, disabled = false, className }: Props) {
  const id = useId();
  return (
    <div className={cn("flex items-start gap-4", className)}>
      <div className="flex flex-1 flex-col gap-1">
        <label htmlFor={id} className="text-body cursor-pointer">
          {label}
        </label>
        {hint ? <p className="text-body-sm text-[var(--color-ink-soft)]">{hint}</p> : null}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-7 w-12 shrink-0 rounded-[var(--radius-pill)] transition-colors duration-[var(--duration-base)] ease-[var(--ease-out-soft)] disabled:cursor-not-allowed disabled:opacity-50",
          /* Azul plano de marca: coherente con Button primary y ProgressDots. */
          checked ? "bg-[var(--color-blue-flat)]" : "bg-[var(--color-border-strong)]",
        )}
      >
        <span
          aria-hidden
          className={cn(
            "absolute top-1 h-5 w-5 rounded-[var(--radius-pill)] bg-white shadow-soft transition-transform duration-[var(--duration-base)] ease-[var(--ease-out-soft)]",
            checked ? "translate-x-[22px]" : "translate-x-1",
          )}
        />
      </button>
    </div>
  );
}
