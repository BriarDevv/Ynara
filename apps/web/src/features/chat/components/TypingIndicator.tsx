import type { CSSProperties } from "react";
import type { ModeId } from "@/components/ui/modes";
import { YnaraOrb } from "@/components/ui/YnaraOrb";

/**
 * Indicador de "Ynara está escribiendo": orbe en modo thinking + 3 puntitos
 * animados con stagger (DESIGN.md §8). Se muestra en `MessageList` mientras
 * `stream.isStreaming` y el assistant aún no tiene texto parcial.
 *
 * a11y: `role="status"` con `aria-label` en el contenedor (role="status"
 * implica aria-live="polite" + aria-atomic="true"). El orbe es `aria-hidden`
 * (decorativo). El lector anuncia la etiqueta del indicador una vez al
 * aparecer, sin repetir cada frame.
 *
 * Reduced-motion: cuando el usuario prefiere movimiento reducido,
 * los puntos animados se ocultan y se muestra un "…" estático.
 */

type Props = {
  modeId: ModeId;
};

export function TypingIndicator({ modeId }: Props) {
  return (
    <div
      role="status"
      aria-label="Ynara está escribiendo"
      className="flex items-center gap-2 px-1 py-2"
    >
      <YnaraOrb size={26} modeId={modeId} thinking />

      {/* Puntos animados — ocultos cuando reduce-motion está activo */}
      <span className="flex items-end gap-[3px] motion-reduce:hidden" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="anim-typing-dot inline-block h-[5px] w-[5px] rounded-full"
            style={
              {
                "--dot-index": i,
                backgroundColor: `var(--mode-${modeId})`,
              } as CSSProperties
            }
          />
        ))}
      </span>

      {/* Fallback estático para reduce-motion (solo visible cuando no hay animación) */}
      <span
        className="hidden motion-reduce:inline text-body text-[var(--color-ink-soft)]"
        aria-hidden="true"
      >
        …
      </span>
    </div>
  );
}
