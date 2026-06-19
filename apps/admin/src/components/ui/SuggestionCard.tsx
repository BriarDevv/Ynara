import type { CSSProperties } from "react";
import { cn } from "@/lib/cn";
import { MODE_BY_ID, type ModeId } from "./modes";

type Props = {
  /** null/undefined → acento neutro (sugerencia transversal, sin modo). */
  modeId?: ModeId | null;
  title: string;
  subtitle?: string;
  /** Con handler es un botón accionable; sin handler, ítem display (`<li>`). */
  onClick?: () => void;
  /** Solo aplica a la variante accionable. */
  disabled?: boolean;
  /** Índice para el stagger de entrada (§8.2). Solo variante display. */
  staggerIndex?: number;
  className?: string;
};

/**
 * Sugerencia tintada por modo (DESIGN.md §3.5/§11). Dos variantes según el
 * uso: con `onClick` es un botón accionable (grid de recomendaciones); sin
 * handler es un ítem display-only (`<li>`, lista "Ynara sugiere" de Hoy).
 * Unificadas acá al deduplicar la copia divergente de `features/today`.
 */
export function SuggestionCard({
  modeId,
  title,
  subtitle,
  onClick,
  disabled = false,
  staggerIndex,
  className,
}: Props) {
  const mode = modeId ? MODE_BY_ID[modeId] : null;
  const accentColor = mode ? mode.tintVar : "var(--color-border-strong)";

  if (!onClick) {
    return (
      // Fila des-encajonada (§12): sin caja, separada por el hairline del `<ul>`
      // padre (`divide-y`). El acento de modo queda como marcador de barra a la
      // izquierda — el único resto cromático de la sugerencia.
      <li
        className={cn(
          "anim-stagger-up flex min-h-[44px] items-stretch gap-3 px-2 py-3.5",
          className,
        )}
        style={{ "--stagger-index": Math.min(staggerIndex ?? 0, 5) } as CSSProperties}
      >
        <span
          aria-hidden
          className="w-1 shrink-0 rounded-full"
          style={{ backgroundColor: accentColor }}
        />
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="text-body font-medium text-[var(--color-ink-deep)]">{title}</span>
          {subtitle ? (
            <span className="text-body-sm text-[var(--color-ink-soft)]">{subtitle}</span>
          ) : null}
        </span>
      </li>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "group relative flex w-full flex-col gap-3 overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)] p-5 text-left transition-[transform,box-shadow,border-color] duration-[var(--duration-base)] ease-[var(--ease-out-soft)] disabled:cursor-not-allowed disabled:opacity-50",
        !disabled &&
          "hover:-translate-y-[1px] hover:border-[var(--color-border-strong)] hover:shadow-soft",
        className,
      )}
    >
      {/* Tint sutil arriba — barra de 3px con el color plano del modo (§3.5) */}
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-[3px]"
        style={{ backgroundColor: accentColor }}
      />
      <span className="flex items-center gap-2">
        <span
          aria-hidden
          className="h-2 w-2 rounded-[var(--radius-pill)]"
          style={{ backgroundColor: accentColor }}
        />
        {mode ? (
          <span className="text-caption text-[var(--color-ink-soft)]">{mode.label}</span>
        ) : null}
      </span>
      <span className="text-subtitle text-[var(--color-ink)]">{title}</span>
      {subtitle ? (
        <span className="text-body-sm text-[var(--color-ink-soft)]">{subtitle}</span>
      ) : null}
    </button>
  );
}
