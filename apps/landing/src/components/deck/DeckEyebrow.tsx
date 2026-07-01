import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * Eyebrow del deck con el DIAMANTE DE PRESENCIA como marcador (en vez de la
 * línea del `.eyebrow` de la landing). El color sale de `--register-accent`
 * (violeta en caos/nodos, azul en calma) que pone la lámina. Es el acento de
 * señal de la identidad puesto al servicio de la navegación del registro.
 */
export function DeckEyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn("deck-eyebrow", className)}>
      <span className="deck-eyebrow__diamond" aria-hidden />
      <span>{children}</span>
    </p>
  );
}
