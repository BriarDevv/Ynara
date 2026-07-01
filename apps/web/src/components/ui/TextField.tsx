import { type InputHTMLAttributes, type Ref, useId, useState } from "react";
import { cn } from "@/lib/cn";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "className"> & {
  label?: string;
  hint?: string;
  /** Mensaje de error inline. Si está presente, marca el campo como inválido. */
  error?: string;
  className?: string;
  /** React 19: `ref` es un prop normal (sin forwardRef). */
  ref?: Ref<HTMLInputElement>;
};

export function TextField({ label, hint, error, id, className, ref, type, ...rest }: Props) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const hintId = hint ? `${fieldId}-hint` : undefined;
  const errorId = error ? `${fieldId}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  const invalid = Boolean(error);

  // Campo de contraseña: el ojito togglea entre ocultar (`password`) y mostrar
  // (`text`). Solo se cablea cuando `type === "password"`; para el resto de los
  // campos el render es el de siempre (sin wrapper, sin botón).
  const isPassword = type === "password";
  const [revealed, setRevealed] = useState(false);
  const effectiveType = isPassword ? (revealed ? "text" : "password") : type;

  const input = (
    <input
      ref={ref}
      id={fieldId}
      type={effectiveType}
      aria-invalid={invalid || undefined}
      aria-describedby={describedBy}
      /*
       * - py-3.5: ~52px alto efectivo; sensación premium sin pasar al
       *   "form gigante" mobile.
       * - pr-12 cuando hay ojito: deja lugar al botón para que el texto no
       *   quede tapado por el ícono.
       * - border default → border-strong en hover; el focus-visible
       *   global aplica el ring de accent encima, no duplicamos foco.
       */
      className={cn(
        "text-body w-full rounded-[var(--radius-md)] border bg-[var(--color-bg)] px-4 py-3.5 text-[var(--color-ink)] placeholder:text-[var(--color-ink-soft)] transition-[border-color,background-color] duration-[var(--duration-base)] ease-[var(--ease-out-soft)]",
        isPassword && "pr-12",
        invalid
          ? "border-[var(--color-error)]"
          : "border-[var(--color-border)] hover:border-[var(--color-border-strong)]",
      )}
      {...rest}
    />
  );

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
      {isPassword ? (
        <div className="relative">
          {input}
          <button
            type="button"
            onClick={() => setRevealed((v) => !v)}
            aria-controls={fieldId}
            aria-pressed={revealed}
            aria-label={revealed ? "Ocultar contraseña" : "Mostrar contraseña"}
            title={revealed ? "Ocultar contraseña" : "Mostrar contraseña"}
            className="absolute inset-y-0 right-0 flex items-center rounded-[var(--radius-md)] px-4 text-[var(--color-ink-soft)] transition-colors hover:text-[var(--color-ink)]"
          >
            {revealed ? <EyeOffIcon /> : <EyeIcon />}
          </button>
        </div>
      ) : (
        input
      )}
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
}

// ---------------------------------------------------------------------------
// Íconos del toggle de contraseña — SVG inline (mismo patrón que el resto de
// la UI: stroke currentColor, sin librería). `aria-hidden`: el estado lo
// comunica el `aria-label` del botón, no el ícono.
// ---------------------------------------------------------------------------

function EyeIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}
