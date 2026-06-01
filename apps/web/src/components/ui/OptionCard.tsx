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
      /*
       * Selected sobrio: ring inset de --color-blue-flat (no fill oscuro).
       * Antes el selected pintaba bg-ink (azul casi negro) con hairline
       * gradient encima — quedaba "pesado" sobre canvas ivory. Ahora el
       * card mantiene fondo blanco y se distingue por el ring azul de
       * marca + sombra más marcada, que se lee como "elegido" sin pisar
       * el lenguaje papel-sobre-canvas.
       *
       * `ring-inset` evita layout shift entre estados (no expande la box
       * por agregar border).
       */
      className={cn(
        "relative w-full rounded-[var(--radius-md)] border bg-[var(--color-bg)] p-4 text-left transition-[transform,box-shadow,border-color] duration-[var(--duration-base)] ease-[var(--ease-out-soft)] disabled:cursor-not-allowed disabled:opacity-50",
        selected
          ? "border-transparent text-[var(--color-ink-deep)] shadow-soft ring-2 ring-inset ring-[var(--color-blue-flat)]"
          : "border-[var(--color-border)] text-[var(--color-ink)] hover:border-[var(--color-border-strong)] hover:shadow-soft",
        className,
      )}
    >
      {/* gap items-center (no items-start) para opciones de 1 línea como las
          de Mood; los hints multi-línea quedan bien por el flex-col interno. */}
      <div className="relative flex items-center gap-3">
        {leading ? <span className="shrink-0">{leading}</span> : null}
        <span className="flex flex-1 flex-col">
          <span className="text-body font-medium text-[var(--color-ink-deep)]">
            {title}
          </span>
          {hint ? (
            <span className="text-body-sm text-[var(--color-ink-soft)]">{hint}</span>
          ) : null}
        </span>
      </div>
    </button>
  );
}
