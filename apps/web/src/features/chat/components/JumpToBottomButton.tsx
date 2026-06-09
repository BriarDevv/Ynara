"use client";

import { Icon } from "@ynara/ui";
import { cn } from "@/lib/cn";

/**
 * Botón flotante "ir al final" del chat (§10 / PR #9). Aparece cuando el
 * usuario se despegó del fondo (scrolleó hacia arriba) y al tocarlo vuelve al
 * fondo. Redondo neutro 44×44 (tap target §12), chevron hacia abajo del set
 * propio — sin glifo de flecha literal (§9). Flota abajo-centro del área de
 * mensajes, justo arriba del composer.
 *
 * El icono es decorativo (`aria-hidden` por default del `Icon`); el botón lleva
 * el `aria-label`. La animación de entrada (`anim-fade-up`) la gatea el CSS por
 * `prefers-reduced-motion` (styles/motion.css), así que no hace falta gatearla acá.
 */
type Props = {
  /** Mostrar el botón. Si es false no se monta (no hay nada que saltar). */
  visible: boolean;
  /** Volver al fondo de la conversación. */
  onClick: () => void;
};

export function JumpToBottomButton({ visible, onClick }: Props) {
  if (!visible) return null;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Ir al final"
      className={cn(
        "anim-fade-up absolute bottom-4 left-1/2 z-10 -translate-x-1/2",
        "flex h-11 w-11 items-center justify-center rounded-[var(--radius-pill)]",
        "border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-ink-soft)] shadow-lifted",
        "transition-[background-color,color] duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
        "hover:bg-[var(--color-bg-soft)] hover:text-[var(--color-ink)]",
      )}
    >
      <Icon name="chevron" size={20} />
    </button>
  );
}
