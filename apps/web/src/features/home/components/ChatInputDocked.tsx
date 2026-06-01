"use client";

import { Icon } from "@ynara/ui";
import { useId } from "react";

/**
 * Input de chat fijo al pie (plan §5.6). Deshabilitado por ahora: es la
 * promesa visual del chat. Muestra un tooltip "Próximamente" al hover/focus
 * y refleja el prefill cuando el usuario elige una recomendación.
 *
 * Se implementa con un botón focusable + `aria-disabled` (en vez de un
 * `<input disabled>`, que no puede recibir foco y no mostraría el tooltip).
 * El tooltip se enlaza al botón vía `aria-describedby` para que también lo
 * anuncien los lectores de pantalla.
 */
type Props = {
  /** Texto prefilleado por una recomendación; vacío = placeholder. */
  value: string;
};

export function ChatInputDocked({ value }: Props) {
  const hasValue = value.trim().length > 0;
  const tooltipId = useId();

  return (
    <div className="sticky bottom-0 left-0 right-0 bg-gradient-to-t from-[var(--color-bg-soft)] via-[var(--color-bg-soft)] to-transparent pt-6 pb-4">
      <div className="group relative mx-auto w-full max-w-[640px]">
        <div
          id={tooltipId}
          role="tooltip"
          className="pointer-events-none absolute -top-9 left-1/2 -translate-x-1/2 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-3 py-1.5 text-caption text-[var(--color-on-dark)] opacity-0 shadow-soft transition-opacity duration-[var(--duration-base)] group-focus-within:opacity-100 group-hover:opacity-100"
        >
          Próximamente
        </div>
        {/* Microinteracción de "promesa": lift sutil en hover/focus del grupo
            (borde + sombra, sin scale por ser full-width), §8.2. No habilita
            nada — el input sigue deshabilitado hasta W5. */}
        <div className="flex items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--color-border)] bg-[var(--color-bg)] p-1.5 shadow-soft transition-[border-color,box-shadow] duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] group-focus-within:border-[var(--color-border-strong)] group-focus-within:shadow-lifted group-hover:border-[var(--color-border-strong)] group-hover:shadow-lifted">
          <button
            type="button"
            aria-disabled="true"
            aria-label="Escribí algo"
            aria-describedby={tooltipId}
            onClick={(e) => e.preventDefault()}
            className="flex-1 cursor-not-allowed truncate rounded-[var(--radius-pill)] px-4 py-2 text-left text-body"
          >
            <span
              className={hasValue ? "text-[var(--color-ink)]" : "text-[var(--color-ink-muted)]"}
            >
              {hasValue ? value : "Escribí algo…"}
            </span>
          </button>
          <span
            aria-hidden
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-pill)] bg-gradient-blue-base text-[var(--color-on-dark)] opacity-50 transition-opacity duration-[var(--duration-fast)] group-hover:opacity-70"
          >
            <Icon name="enviar" size={18} />
          </span>
        </div>
      </div>
    </div>
  );
}
