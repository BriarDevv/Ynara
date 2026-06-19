"use client";

import { type ColumnPlacement, layoutColumns } from "@ynara/core/features/agenda";
import { useEffect, useRef } from "react";
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
  /** Tocar un evento abre el sheet de edición. */
  onEventClick: (event: AgendaEvent) => void;
};

type EventBlockProps = {
  event: AgendaEvent;
  rowPx: number;
  /** Primera hora visible de la grilla (origen del posicionado). */
  minH: number;
  /** Columna asignada por el algoritmo de solapamiento (lado-a-lado). */
  placement: ColumnPlacement;
  onEventClick: (event: AgendaEvent) => void;
};

/**
 * Bloque de evento posicionado absolute dentro de la grilla. Es un `<button>`
 * clickeable (mouse/touch) — pero `tabIndex={-1}` y el grid es `aria-hidden`: la
 * edición por teclado/lector va por la vista Lista (que cubre la semana actual;
 * los eventos de otras semanas quedan solo con mouse acá — deuda de a11y).
 */
function GridEventBlock({ event, rowPx, minH, placement, onEventClick }: EventBlockProps) {
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
    <button
      type="button"
      tabIndex={-1}
      onClick={() => onEventClick(event)}
      className={cn(
        "absolute flex gap-2 overflow-hidden rounded-[var(--radius-md)] px-2 py-1 text-left",
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
    </button>
  );
}

type GridProps = {
  /** Eventos YA filtrados al día (vienen de `eventsForDay` en `DayView`). */
  events: AgendaEvent[];
  day: Date;
  now: Date;
  rowPx: number;
  onEventClick: (event: AgendaEvent) => void;
};

function DayGrid({ events, day, now, rowPx, onEventClick }: GridProps) {
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

  // Scroll-to-now: deja la hora actual ~1/3 desde arriba si es hoy; si no, el
  // inicio laboral (8h). No roba foco (scrollTop programático). `focusHour`
  // deriva de `now` (fijada en montaje) → estable, así re-scrollea solo al
  // navegar de día (o un refetch que cambie el rango), no en cada render;
  // `nowHour()` (live) queda para la línea "ahora".
  const scrollRef = useRef<HTMLDivElement>(null);
  const focusHour = isToday ? now.getHours() + now.getMinutes() / 60 : Math.max(minH, 8);
  useEffect(() => {
    const el = scrollRef.current;
    if (!el || el.clientHeight === 0) return; // copia oculta (display:none) → no-op
    const target = (focusHour - minH) * rowPx;
    el.scrollTop = Math.max(0, target - el.clientHeight / 3);
  }, [focusHour, minH, rowPx]);

  return (
    <div
      ref={scrollRef}
      className="max-h-[60vh] overflow-y-auto overflow-x-hidden overscroll-contain"
    >
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
              onEventClick={onEventClick}
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
    </div>
  );
}

/**
 * Vista **día** — grilla horaria con eventos posicionados `absolute`, teñidos
 * por modo, y línea "ahora" si el día es hoy. La ventana horaria es auto-fit
 * (base 8–20h, se expande para incluir eventos fuera de ese rango — cero
 * recorte). La grilla vive en un contenedor de alto fijo (`max-h-[60vh]`) con
 * scroll propio, que al montar arranca en la hora actual (scroll-to-now) o en
 * el inicio laboral. Responsive: 52 px/hora en desktop, 36 px/hora en mobile.
 */
export function DayView({ events, day, now, onEventClick }: Props) {
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
          <DayGrid
            events={dayEvents}
            day={day}
            now={now}
            rowPx={ROW_MOBILE}
            onEventClick={onEventClick}
          />
        </div>
        {/* Desktop */}
        <div className="hidden md:block">
          <DayGrid
            events={dayEvents}
            day={day}
            now={now}
            rowPx={ROW_DESKTOP}
            onEventClick={onEventClick}
          />
        </div>
      </div>
    </>
  );
}
