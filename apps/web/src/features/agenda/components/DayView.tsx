import { type ColumnPlacement, layoutColumns } from "@ynara/core/features/agenda";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { MODE_BY_ID } from "@/components/ui/modes";
import { cn } from "@/lib/cn";
import type { AgendaEvent } from "../api";
import {
  eventsForDay,
  formatEventRange,
  gridHeight,
  gridTop,
  hourBounds,
  nowHour,
  toLayoutInterval,
} from "../format";
import { formatDayLong, isSameDay } from "../labels";

// ── Constantes de la grilla ─────────────────────────────────────────────────
// La ventana horaria sale de `hourBounds` (base 8–20h, auto-fit a los eventos).
const ROW_DESKTOP = 52; // px por hora en desktop
const ROW_MOBILE = 36; // px por hora en mobile (< md)
const LEFT_GUTTER = 40; // ancho de la columna de horas (px)

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
  /** Primera hora visible de la grilla (origen del posicionado). */
  minH: number;
  /** Columna asignada por el algoritmo de solapamiento (lado-a-lado). */
  placement: ColumnPlacement;
};

/** Bloque de evento posicionado absolute dentro de la grilla. */
function GridEventBlock({ event, rowPx, minH, placement }: EventBlockProps) {
  const tintVar = event.mode ? MODE_BY_ID[event.mode].tintVar : "var(--color-border-strong)";
  const cancelled = event.status === "cancelled";
  const tentative = event.status === "tentative";

  const top = gridTop(event, minH, rowPx);
  const height = gridHeight(event, rowPx, rowPx * 0.4);

  // Ancho/posición horizontal según la columna del cluster (2px de gap a cada
  // lado). Un evento sin solapes ocupa el ancho completo (cols = 1).
  const widthPct = 100 / placement.cols;
  const leftPct = placement.col * widthPct;

  const start = new Date(event.start_at);
  const end = new Date(start.getTime() + event.duration_min * 60_000);
  const hhmm = (d: Date) =>
    `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;

  return (
    <article
      className={cn(
        "absolute flex gap-2 overflow-hidden rounded-[var(--radius-md)] px-2 py-1",
        tentative ? "border border-dashed border-[var(--color-border-strong)]" : "",
        cancelled && "opacity-50",
      )}
      style={{
        top,
        height,
        left: `calc(${leftPct}% + 2px)`,
        width: `calc(${widthPct}% - 4px)`,
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
  /** Eventos YA filtrados al día (vienen de `eventsForDay` en `DayView`). */
  events: AgendaEvent[];
  day: Date;
  now: Date;
  rowPx: number;
};

function DayGrid({ events, day, now, rowPx }: GridProps) {
  // Ventana horaria auto-fit: base 8–20h expandida a los eventos del día (cero
  // recorte). Antes era fija 8–20h y clipeaba los de madrugada/noche.
  const { minH, maxH } = hourBounds(events, [day]);
  const hours = Array.from({ length: maxH - minH + 1 }, (_, i) => minH + i);

  const nh = nowHour();
  const isToday = isSameDay(day, now);
  const showNowLine = isToday && nh >= minH && nh <= maxH;
  const nowTop = (nh - minH) * rowPx;

  const totalHeight = (maxH - minH) * rowPx;
  // Columnas para los solapados: el algoritmo puro de core devuelve {col, cols}.
  const placements = layoutColumns(events.map(toLayoutInterval));

  return (
    <div className="relative" style={{ paddingLeft: LEFT_GUTTER, height: totalHeight }}>
      {/* Líneas horizontales + etiquetas de hora */}
      {hours.map((h) => (
        <div
          key={h}
          aria-hidden
          className="pointer-events-none absolute inset-x-0"
          style={{ top: (h - minH) * rowPx }}
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
        {events.map((event) => (
          <GridEventBlock
            key={event.id}
            event={event}
            rowPx={rowPx}
            minH={minH}
            placement={placements.get(event.id) ?? { col: 0, cols: 1 }}
          />
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
 * Vista **día** — grilla horaria con eventos posicionados `absolute`, teñidos
 * por modo, y línea "ahora" si el día es hoy. La ventana horaria es auto-fit
 * (base 8–20h, se expande para incluir eventos fuera de ese rango — cero
 * recorte). Responsive: 52 px/hora en desktop, 36 px/hora en mobile.
 */
export function DayView({ events, day, now }: Props) {
  const dayEvents = eventsForDay(events, day);

  if (dayEvents.length === 0 && !isSameDay(day, now)) {
    return <EmptyStateCard title="Nada agendado este día" hint="Tenés el día libre." />;
  }

  return (
    <>
      {/* Alternativa accesible: la grilla visual es aria-hidden (representación
          espacial que no linealiza); este resumen sr-only expone los mismos
          eventos del día a lectores de pantalla, uno por ítem de lista. Mismo
          patrón que WeekView. */}
      <ul className="sr-only" aria-label={`Eventos de ${formatDayLong(day)}`}>
        {dayEvents.length === 0 ? (
          <li>Sin eventos</li>
        ) : (
          dayEvents.map((event) => (
            <li key={event.id}>
              {event.title}, {formatEventRange(event)}
              {event.mode ? `, modo ${MODE_BY_ID[event.mode].label}` : ""}
              {event.location ? `, en ${event.location}` : ""}
              {event.status === "cancelled" ? ", cancelado" : ""}
            </li>
          ))
        )}
      </ul>

      <div className="relative overflow-x-hidden" aria-hidden>
        {/* Mobile */}
        <div className="md:hidden">
          <DayGrid events={dayEvents} day={day} now={now} rowPx={ROW_MOBILE} />
        </div>
        {/* Desktop */}
        <div className="hidden md:block">
          <DayGrid events={dayEvents} day={day} now={now} rowPx={ROW_DESKTOP} />
        </div>
      </div>
    </>
  );
}
