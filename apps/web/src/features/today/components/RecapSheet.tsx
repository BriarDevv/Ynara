import { Sheet } from "@/components/ui/Sheet";
import type { Recap } from "../api";
import { formatHoyDate } from "../format";

type Props = {
  open: boolean;
  onClose: () => void;
  recap: Recap;
};

/**
 * Sheet del recap del día (wireframe 15 / build-plan E4): el borrador que Ynara
 * armó del día — un headline editorial + los highlights. Cerrar el día de
 * verdad (regenerar con el LLM, marcar `pending: false`) es la Fase H2 /
 * backend; acá se muestra el borrador y se puede cerrar el sheet.
 */
export function RecapSheet({ open, onClose, recap }: Props) {
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Recap del día"
      description={formatHoyDate(new Date(recap.date))}
    >
      <div className="flex flex-col gap-5">
        {recap.headline ? (
          <p className="text-subtitle text-[var(--color-ink)]">{recap.headline}</p>
        ) : null}

        {recap.highlights.length > 0 ? (
          <ul className="flex flex-col gap-3">
            {recap.highlights.map((highlight) => (
              <li key={highlight} className="flex items-start gap-3">
                <span
                  aria-hidden
                  className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-ink-faint)]"
                />
                <span className="text-body text-[var(--color-ink-soft)]">{highlight}</span>
              </li>
            ))}
          </ul>
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
          Listo
        </button>
      </div>
    </Sheet>
  );
}
