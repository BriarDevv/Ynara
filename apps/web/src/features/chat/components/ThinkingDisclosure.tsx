"use client";

import { Icon } from "@ynara/ui";
import { useId, useState } from "react";

/**
 * Colapsable "Pensando…" — muestra el razonamiento post-hoc del modelo (Camino
 * A, evento SSE `reasoning`) arriba de la respuesta. Lo monta `MessageBubble`
 * solo cuando hay `reasoning` y el toggle display-only está ON.
 *
 * Comportamiento:
 *  - Mientras el modelo "piensa" (`streaming` = stream abierto y la respuesta
 *    todavía sin texto), el colapsable arranca ABIERTO: se ve el pensamiento en
 *    vivo.
 *  - Al llegar el texto de la respuesta (`streaming` → false), auto-COLAPSA: el
 *    foco pasa a la respuesta. El usuario puede re-expandir con el botón.
 *  - El razonamiento se renderiza como TEXTO PLANO (no markdown ejecutable).
 *
 * a11y: patrón disclosure (botón con `aria-expanded` + `aria-controls` sobre la
 * región). La región se oculta de lectores cuando está colapsada
 * (`aria-hidden`). Transiciones suaves vía grid-rows 0fr↔1fr + rotación del
 * chevron, desactivadas con `prefers-reduced-motion`.
 */
type Props = {
  /** Razonamiento acumulado (plain text). */
  reasoning: string;
  /**
   * True mientras el modelo piensa (stream abierto, respuesta aún sin texto).
   * Maneja el auto-abierto/auto-colapso; entre transiciones el toggle manual
   * del usuario tiene prioridad (re-expandible).
   */
  streaming: boolean;
};

export function ThinkingDisclosure({ reasoning, streaming }: Props) {
  const regionId = useId();
  const [open, setOpen] = useState(streaming);

  // Patrón oficial de React (ajustar estado cuando una prop cambia, igual que
  // MessageList con el anuncio a11y): cuando `streaming` cambia, sincronizamos
  // el `open` con el auto (abierto mientras piensa, colapsado al llegar la
  // respuesta). Entre transiciones, el click del usuario manda.
  const [prevStreaming, setPrevStreaming] = useState(streaming);
  if (streaming !== prevStreaming) {
    setPrevStreaming(streaming);
    setOpen(streaming);
  }

  return (
    <div data-testid="thinking-disclosure" className="mb-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={regionId}
        className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-2 py-1 text-caption text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-bg-soft)] hover:text-[var(--color-ink)]"
      >
        <span
          aria-hidden
          className="inline-flex transition-transform duration-[var(--duration-fast)] motion-reduce:transition-none"
          style={{ transform: open ? "rotate(0deg)" : "rotate(-90deg)" }}
        >
          <Icon name="chevron" size={12} />
        </span>
        <span>{streaming ? "Pensando…" : "Cómo lo pensé"}</span>
      </button>

      {/* Grid-rows 0fr→1fr: colapso suave de alto desconocido sin medir el DOM.
          `overflow-hidden` clipea el contenido mientras se anima. */}
      <div
        className="grid transition-[grid-template-rows] duration-[var(--duration-base)] ease-[var(--ease-out-soft)] motion-reduce:transition-none"
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          <p
            id={regionId}
            aria-hidden={!open}
            className="mt-1 whitespace-pre-wrap rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] px-3 py-2 text-body-sm text-[var(--color-ink-soft)]"
          >
            {reasoning}
          </p>
        </div>
      </div>
    </div>
  );
}
