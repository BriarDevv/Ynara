"use client";

import {
  type ColumnPlacement,
  dragStart,
  layoutColumns,
  resizeDuration,
} from "@ynara/core/features/agenda";
import { type PointerEvent as ReactPointerEvent, useEffect, useRef, useState } from "react";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { MODE_BY_ID } from "@/components/ui/modes";
import { cn } from "@/lib/cn";
import { type AgendaEvent, usePatchEventById } from "../api";
import { eventsForDay, formatEventRange, hourBounds, nowHour, toLayoutInterval } from "../format";
import { formatDayLong, isSameDay } from "../labels";

/** Minutos del día (local) del inicio de un evento. */
function startMinOf(event: AgendaEvent): number {
  const d = new Date(event.start_at);
  return d.getHours() * 60 + d.getMinutes();
}

/**
 * ISO del evento con el inicio movido a `startMin` (mismo día, hora local).
 * TODO(tz): usa `setHours` sobre el `Date` local → en un borde de DST podría
 * correr 1h. Cuando el evento traiga `time_zone` (ADR-018), recalcular en ese
 * huso con Temporal (ya entra por `expand.ts`). Mock-first hoy no lo expone.
 */
function isoWithStartMin(originalIso: string, startMin: number): string {
  const d = new Date(originalIso);
  d.setHours(Math.floor(startMin / 60), startMin % 60, 0, 0);
  return d.toISOString();
}

const hhmm = (d: Date) =>
  `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;

/** Cambios que el drag puede commitear sobre un evento. */
type EventTimePatch = { start_at?: string; duration_min?: number };

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
  /** Commit del drag (mover / redimensionar) sobre el evento. */
  onCommit: (id: string, patch: EventTimePatch) => void;
};

type DragState = {
  kind: "move" | "resize";
  pointerY: number;
  startMin: number;
  durMin: number;
  /** ¿Pasó el umbral de movimiento? (si no, el pointerup es un tap → editar). */
  moved: boolean;
};

const MOVE_THRESHOLD_PX = 4;

/**
 * Bloque de evento posicionado absolute dentro de la grilla. `<button>`
 * clickeable (mouse/touch) con `tabIndex={-1}` bajo el grid `aria-hidden`: la
 * edición por teclado/lector va por la vista Lista (que cubre la semana actual;
 * los de otras semanas quedan solo con mouse acá — deuda de a11y).
 *
 * **Drag:** arrastrar el cuerpo lo mueve; el handle inferior lo redimensiona. El
 * cálculo (snap a 15min, clamp al día) es puro (`@ynara/core`); acá va solo el
 * binding de pointer-events + el preview local. Un tap (sin movimiento real)
 * abre el sheet de edición.
 */
function GridEventBlock({
  event,
  rowPx,
  minH,
  placement,
  onEventClick,
  onCommit,
}: EventBlockProps) {
  const tintVar = event.mode ? MODE_BY_ID[event.mode].tintVar : "var(--color-border-strong)";
  const cancelled = event.status === "cancelled";
  const tentative = event.status === "tentative";

  const baseStartMin = startMinOf(event);
  const [drag, setDrag] = useState<DragState | null>(null);

  // Posición efectiva: preview durante el drag, real si no.
  const startMin = drag ? drag.startMin : baseStartMin;
  const durMin = drag ? drag.durMin : event.duration_min;

  const top = (startMin / 60 - minH) * rowPx;
  const height = Math.max(rowPx * 0.4, (durMin / 60) * rowPx);
  const widthPct = 100 / placement.cols;
  const leftPct = placement.col * widthPct;

  // Hora mostrada (sigue al preview durante el drag).
  const start = new Date(event.start_at);
  start.setHours(Math.floor(startMin / 60), startMin % 60, 0, 0);
  const end = new Date(start.getTime() + durMin * 60_000);

  function handlePointerDown(e: ReactPointerEvent<HTMLButtonElement>) {
    if (e.pointerType === "mouse" && e.button !== 0) return; // solo botón primario
    const isResize = (e.target as HTMLElement).dataset.resizeHandle === "true";
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag({
      kind: isResize ? "resize" : "move",
      pointerY: e.clientY,
      startMin: baseStartMin,
      durMin: event.duration_min,
      moved: false,
    });
  }

  function handlePointerMove(e: ReactPointerEvent<HTMLButtonElement>) {
    // Los all-day no se arrastran en el time-grid (mover/redimensionar los
    // convertiría en timed): se ignora el movimiento → el pointerup queda como
    // tap (abre el sheet). `moved` nunca pasa a true.
    if (!drag || event.all_day) return;
    const deltaY = e.clientY - drag.pointerY;
    const moved = drag.moved || Math.abs(deltaY) > MOVE_THRESHOLD_PX;
    if (drag.kind === "move") {
      const next = dragStart(baseStartMin, deltaY, rowPx, event.duration_min);
      setDrag({ ...drag, startMin: next, moved });
    } else {
      const next = resizeDuration(event.duration_min, deltaY, rowPx, baseStartMin);
      setDrag({ ...drag, durMin: next, moved });
    }
  }

  function handlePointerUp(e: ReactPointerEvent<HTMLButtonElement>) {
    if (!drag) return;
    e.currentTarget.releasePointerCapture(e.pointerId);
    const finished = drag;
    setDrag(null);
    if (!finished.moved) {
      onEventClick(event); // tap → editar
      return;
    }
    if (finished.kind === "move" && finished.startMin !== baseStartMin) {
      onCommit(event.id, { start_at: isoWithStartMin(event.start_at, finished.startMin) });
    } else if (finished.kind === "resize" && finished.durMin !== event.duration_min) {
      onCommit(event.id, { duration_min: finished.durMin });
    }
  }

  return (
    <button
      type="button"
      tabIndex={-1}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={() => setDrag(null)}
      className={cn(
        "absolute flex touch-none select-none gap-2 overflow-hidden rounded-[var(--radius-md)] px-2 py-1 text-left",
        tentative ? "border border-dashed border-[var(--color-border-strong)]" : "",
        cancelled && "opacity-50",
        drag?.moved && "z-20 shadow-lifted",
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
      {/* Handle de resize (borde inferior) */}
      <span
        aria-hidden
        data-resize-handle="true"
        className="absolute inset-x-0 bottom-0 h-2 cursor-ns-resize"
      />
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
  onCommit: (id: string, patch: EventTimePatch) => void;
};

function DayGrid({ events, day, now, rowPx, onEventClick, onCommit }: GridProps) {
  // Tick de 1 minuto para que `nowHour()` (la línea de "ahora") siga la hora
  // real (sin esto quedaba congelada en el montaje). El `setInterval` se arma
  // en el effect de abajo, gateado por `isToday` + copia visible.
  const [, setNowTick] = useState(0);

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

  // Tick de la línea de "ahora": solo si es hoy y solo en la copia visible (la
  // oculta tiene clientHeight 0, mismo guard que el scroll) — así no corren dos
  // timers (mobile + desktop) ni se tickea cuando la línea ni se muestra.
  useEffect(() => {
    if (!isToday || scrollRef.current?.clientHeight === 0) return;
    const id = setInterval(() => setNowTick((n) => n + 1), 60_000);
    return () => clearInterval(id);
  }, [isToday]);

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
              onCommit={onCommit}
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
  // Commit del drag (mover/redimensionar): patch por id, optimista-vía-refetch.
  const patch = usePatchEventById();
  const onCommit = (id: string, p: EventTimePatch) => patch.mutate({ id, patch: p });

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
            onCommit={onCommit}
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
            onCommit={onCommit}
          />
        </div>
      </div>
    </>
  );
}
