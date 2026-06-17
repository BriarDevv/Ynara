import type { CSSProperties } from "react";
import { MODE_BY_ID } from "@/components/ui/modes";
import { cn } from "@/lib/cn";
import type { AgendaEvent } from "../api";
import { formatEventRange } from "../format";

type Props = {
  event: AgendaEvent;
  /** Índice en la lista, para el stagger de entrada (§8.2). */
  index: number;
};

/** Etiqueta del estado no-confirmado (el confirmado no lleva tag). */
const STATUS_LABEL: Record<"tentative" | "cancelled", string> = {
  tentative: "Tentativo",
  cancelled: "Cancelado",
};

/**
 * Un bloque de la Agenda (wireframes 10/11): el rango horario derivado
 * ("10:00 – 11:30") + el título + el lugar opcional, con un *spine* a la
 * izquierda teñido por el modo del evento (o el borde neutro si es transversal).
 * `tentative` → borde punteado + tag; `cancelled` → título tachado + atenuado.
 */
export function EventBlock({ event, index }: Props) {
  const tintVar = event.mode ? MODE_BY_ID[event.mode].tintVar : "var(--color-border-strong)";
  const cancelled = event.status === "cancelled";
  const tentative = event.status === "tentative";

  return (
    <li
      className="anim-stagger-up"
      style={{ "--stagger-index": Math.min(index, 5) } as CSSProperties}
    >
      <article
        className={cn(
          "flex gap-3 rounded-[var(--radius-lg)] border bg-[var(--color-bg)] p-3.5",
          tentative
            ? "border-dashed border-[var(--color-border-strong)]"
            : "border-[var(--color-border)]",
          cancelled && "opacity-60",
        )}
      >
        <span
          aria-hidden
          className="w-1 shrink-0 self-stretch rounded-full"
          style={{ backgroundColor: tintVar }}
        />
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="text-body-sm tabular-nums text-[var(--color-ink-soft)]">
            {formatEventRange(event)}
          </span>
          <span
            className={cn(
              "text-body",
              cancelled ? "text-[var(--color-ink-soft)] line-through" : "text-[var(--color-ink)]",
            )}
          >
            {event.title}
          </span>
          {event.location ? (
            <span className="text-body-sm text-[var(--color-ink-soft)]">{event.location}</span>
          ) : null}
          {event.status !== "confirmed" ? (
            <span className="text-caption text-[var(--color-ink-soft)]">
              {STATUS_LABEL[event.status]}
            </span>
          ) : null}
        </div>
      </article>
    </li>
  );
}
