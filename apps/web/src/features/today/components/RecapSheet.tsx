"use client";

import { Diamond } from "@/components/ui/Diamond";
import { Sheet } from "@/components/ui/Sheet";
import { YnaraOrb } from "@/components/ui/YnaraOrb";
import { useActiveMode } from "@/hooks/useActiveMode";
import type { Recap } from "../api";
import { formatHoyDate } from "../format";

type Props = {
  open: boolean;
  onClose: () => void;
  recap: Recap;
};

/**
 * Sheet del recap del día (wireframe 15 / build-plan E4): header con orbe +
 * fecha e insights reales (los ``highlights`` que devuelve ``GET /v1/recap``,
 * derivados de las tareas del usuario) con Diamond como bullet. Las cifras grandes
 * mock se quitaron: el contrato del recap (`RecapSchema`) no las declara, así que
 * mostrarlas era data falsa. (La voz/cifras LLM son la próxima fase, roadmap F.)
 */
export function RecapSheet({ open, onClose, recap }: Props) {
  const activeMode = useActiveMode();

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Recap del día"
      titleHidden
      description={formatHoyDate(new Date(recap.date))}
    >
      <div className="flex flex-col gap-6">
        {/* Header: orbe + fecha + título */}
        <div className="flex items-center gap-3.5">
          <YnaraOrb size={42} modeId={activeMode} />
          <div className="min-w-0">
            <p className="text-caption uppercase tracking-[.14em] text-[var(--color-ink-soft)]">
              {formatHoyDate(new Date(recap.date))}
            </p>
            <h2 className="mt-0.5 text-[1.4rem] font-semibold leading-[1.05] tracking-tight text-[var(--color-ink)]">
              {recap.headline || "Cómo te fue hoy"}
            </h2>
          </div>
        </div>

        {/* Insights: label + lista con Diamond como bullet */}
        {recap.highlights.length > 0 ? (
          <div>
            <p className="mb-2 text-[11px] font-bold uppercase tracking-[.14em] text-[var(--color-ink-soft)]">
              Ynara observó
            </p>
            <ul className="flex flex-col">
              {recap.highlights.map((highlight, i) => (
                <li
                  key={highlight}
                  className="flex items-start gap-3 py-2.5"
                  style={
                    i < recap.highlights.length - 1
                      ? { borderBottom: "1px solid var(--color-border)" }
                      : undefined
                  }
                >
                  <span className="mt-[5px] shrink-0">
                    <Diamond size={9} color="var(--color-blue-flat)" />
                  </span>
                  <span className="text-body text-[var(--color-ink)]">{highlight}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-body text-[var(--color-ink-soft)]">
            Todavía no hay nada para repasar. A medida que pase el día, esto se llena.
          </p>
        )}

        <button
          type="button"
          onClick={onClose}
          className="text-button mt-1 self-start rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)] px-5 py-2.5 text-[var(--color-ink)] transition-colors duration-[var(--duration-fast)] hover:bg-[var(--color-border)]"
        >
          Cerrar el día
        </button>
      </div>
    </Sheet>
  );
}
