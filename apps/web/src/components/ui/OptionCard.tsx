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
       * La definición de la card viene del BORDE (border-2), no de la diferencia
       * de fondo: el StepShell de desktop es una card `--color-bg` y en claro
       * `bg-soft` ≈ blanco, así que un hairline tenue no alcanzaba (la opción
       * "no se veía"). El ring de Tailwind tampoco renderizaba el estado
       * seleccionado. Reposo: borde gris medio (`ink-muted`). Seleccionado:
       * borde de marca theme-aware (`selected-ring`: azul en claro, celeste en
       * Noche, porque el azul oscuro no contrasta como línea sobre navy).
       */
      className={cn(
        // Borde de 2px que SIEMPRE renderiza (no dependemos del ring de Tailwind
        // ni de que bg-soft contraste con el contenedor — en claro bg-soft ≈
        // blanco). Reposo: gris medio (`ink-muted`). Seleccionado: color de
        // marca theme-aware (`selected-ring`). `border-2` en ambos estados →
        // sin layout shift.
        "relative w-full rounded-[var(--radius-md)] border-2 bg-[var(--color-bg-soft)] p-4 text-left transition-[transform,box-shadow,border-color] duration-[var(--duration-base)] ease-[var(--ease-out-soft)] disabled:cursor-not-allowed disabled:opacity-50",
        selected
          ? "border-[var(--color-selected-ring)] text-[var(--color-ink-deep)] shadow-soft"
          : "border-[var(--color-ink-muted)] text-[var(--color-ink)] hover:border-[var(--color-ink)] hover:shadow-soft",
        className,
      )}
    >
      {/* gap items-center (no items-start) para opciones de 1 línea como las
          de Mood; los hints multi-línea quedan bien por el flex-col interno. */}
      <div className="relative flex items-center gap-3">
        {leading ? <span className="shrink-0">{leading}</span> : null}
        <span className="flex flex-1 flex-col">
          <span className="text-body font-medium text-[var(--color-ink-deep)]">{title}</span>
          {hint ? <span className="text-body-sm text-[var(--color-ink-soft)]">{hint}</span> : null}
        </span>
      </div>
    </button>
  );
}
