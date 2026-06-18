import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { MODE_BY_ID } from "@/components/ui/modes";
import { cn } from "@/lib/cn";
import type { AgendaEvent } from "../api";
import { eventsForDay, gridHeight, gridTop, isInRange, nowHour } from "../format";
import { isSameDay } from "../labels";

// ── Constantes de la grilla ─────────────────────────────────────────────────
const H0 = 8; // primera hora visible
const H1 = 20; // última hora visible
const ROW_DESKTOP = 52; // px por hora en desktop
const ROW_MOBILE = 36; // px por hora en mobile (< md)
const LEFT_GUTTER = 40; // ancho de la columna de horas (px)
const HOURS = Array.from({ length: H1 - H0 + 1 }, (_, i) => H0 + i);

type Props = {
  events: AgendaEvent[];
  /** Día que se está mirando. */
  day: Date;
  /** Referencia de "ahora" (fijada en montaje). */
  now: Date;
};

type EventBlockProps = {
  event: AgendaEvent;
  rowPx: number;
};

/** Bloque de evento posicionado absolute dentro de la grilla. */
function GridEventBlock({ event, rowPx }: EventBlockProps) {
  const tintVar = event.mode ? MODE_BY_ID[event.mode].tintVar : "var(--color-border-strong)";
  const cancelled = event.status === "cancelled";
  const tentative = event.status === "tentative";

  const top = gridTop(event, H0, rowPx);
  const height = gridHeight(event, rowPx, rowPx * 0.4);

  const start = new Date(event.start_at);
  const end = new Date(start.getTime() + event.duration_min * 60_000);
  const hhmm = (d: Date) =>
    `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;

  return (
    <article
      className={cn(
        "absolute inset-x-1 flex gap-2 overflow-hidden rounded-[var(--radius-md)] px-2 py-1",
        tentative ? "border border-dashed border-[var(--color-border-strong)]" : "",
        cancelled && "opacity-50",
      )}
      style={{
        top,
        height,
        backgroundColor: `color-mix(in srgb, ${tintVar} 15%, var(--color-bg))`,
      }}
    >
      {/* Spine de color del modo */}
      <span
        aria-hidden
        className="w-0.5 shrink-0 self-stretch rounded-full"
        style={{ backgroundColor: tintVar }}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <span
          className={cn(
            "text-body-sm font-semibold leading-tight text-[var(--color-ink)]",
            cancelled && "line-through",
          )}
        >
          {event.title}
        </span>
        {height >= rowPx * 0.7 ? (
          <span className="text-caption tabular-nums text-[var(--color-ink-soft)]">
            {hhmm(start)}–{hhmm(end)}
          </span>
        ) : null}
      </div>
    </article>
  );
}

type GridProps = {
  events: AgendaEvent[];
  day: Date;
  now: Date;
  rowPx: number;
};

function DayGrid({ events, day, now, rowPx }: GridProps) {
  const nh = nowHour();
  const isToday = isSameDay(day, now);
  const showNowLine = isToday && nh >= H0 && nh <= H1;
  const nowTop = (nh - H0) * rowPx;

  const totalHeight = (H1 - H0) * rowPx;
  const visibleEvents = events.filter((e) => isInRange(e, H0, H1));

  return (
    <div className="relative" style={{ paddingLeft: LEFT_GUTTER, height: totalHeight }}>
      {/* Líneas horizontales + etiquetas de hora */}
      {HOURS.map((h) => (
        <div
          key={h}
          aria-hidden
          className="pointer-events-none absolute inset-x-0"
          style={{ top: (h - H0) * rowPx }}
        >
          {/* Etiqueta de hora */}
          <span className="absolute right-full top-[-7px] w-8 pr-2 text-right text-[12px] font-semibold leading-none tabular-nums text-[var(--color-ink-soft)]">
            {String(h).padStart(2, "0")}
          </span>
          {/* Línea fina */}
          <div className="h-px w-full bg-[var(--color-border)]" />
        </div>
      ))}

      {/* Columna de eventos (relative para los bloques absolute) */}
      <div className="absolute inset-0" style={{ left: LEFT_GUTTER }}>
        {visibleEvents.map((event) => (
          <GridEventBlock key={event.id} event={event} rowPx={rowPx} />
        ))}

        {/* Línea "ahora" */}
        {showNowLine && (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 z-10"
            style={{ top: nowTop }}
          >
            {/* Dot */}
            <span
              className="absolute -left-1.5 -top-1.5 h-3 w-3 rounded-full"
              style={{ backgroundColor: "var(--color-accent)" }}
            />
            {/* Línea */}
            <div
              className="absolute inset-x-0 h-0.5"
              style={{ backgroundColor: "var(--color-accent)" }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Vista **día** — grilla horaria 08–20h con eventos posicionados `absolute`,
 * teñidos por modo, y línea "ahora" si el día es hoy. Responsive: 52 px/hora
 * en desktop, 36 px/hora en mobile.
 */
export function DayView({ events, day, now }: Props) {
  const dayEvents = eventsForDay(events, day);

  if (dayEvents.length === 0 && !isSameDay(day, now)) {
    return <EmptyStateCard title="Nada agendado este día" hint="Tenés el día libre." />;
  }

  return (
    <div className="relative overflow-x-hidden">
      {/* Mobile */}
      <div className="md:hidden">
        <DayGrid events={dayEvents} day={day} now={now} rowPx={ROW_MOBILE} />
      </div>
      {/* Desktop */}
      <div className="hidden md:block">
        <DayGrid events={dayEvents} day={day} now={now} rowPx={ROW_DESKTOP} />
      </div>
    </div>
  );
}
