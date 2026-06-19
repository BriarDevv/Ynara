import { type ColumnPlacement, layoutColumns } from "@ynara/core/features/agenda";
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
  weekDays,
} from "../format";
import { formatDayLong, formatDayNum, formatWeekdayShort, isSameDay } from "../labels";

// ── Constantes de la grilla ─────────────────────────────────────────────────
// La ventana horaria sale de `hourBounds` (base 8–20h, auto-fit a los eventos).
const PXH = 44; // px por hora (la grilla es desktop-only)
const LEFT_GUTTER = 30; // ancho de la columna de horas (px)

type Props = {
  events: AgendaEvent[];
  /** Cualquier día de la semana a mostrar (se normaliza a lunes→domingo). */
  anchor: Date;
  /** Referencia de "ahora" para marcar el día de hoy. */
  now: Date;
  /** Tocar un evento abre el sheet de edición. */
  onEventClick: (event: AgendaEvent) => void;
};

const hhmm = (d: Date) =>
  `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;

type ColEventProps = {
  event: AgendaEvent;
  minH: number;
  /** Columna asignada por el algoritmo de solapamiento (lado-a-lado). */
  placement: ColumnPlacement;
  onEventClick: (event: AgendaEvent) => void;
};

/** Barra de evento (botón) posicionada absolute dentro de su columna. Clickeable
 *  con mouse/touch pero `tabIndex={-1}` y `aria-hidden`: la edición por teclado/
 *  lector va por la vista Lista; este grid es una representación espacial. */
function ColEvent({ event, minH, placement, onEventClick }: ColEventProps) {
  const tintVar = event.mode ? MODE_BY_ID[event.mode].tintVar : "var(--color-border-strong)";
  const cancelled = event.status === "cancelled";
  const tentative = event.status === "tentative";
  const top = gridTop(event, minH, PXH);
  const height = gridHeight(event, PXH, 24);

  // Sub-columnas dentro de la columna del día para los solapados (gap 1px). Un
  // evento sin solapes ocupa el ancho completo del día (cols = 1).
  const widthPct = 100 / placement.cols;
  const leftPct = placement.col * widthPct;

  return (
    <button
      type="button"
      aria-hidden
      tabIndex={-1}
      onClick={() => onEventClick(event)}
      title={event.title}
      className={cn(
        "absolute flex flex-col gap-px overflow-hidden rounded-[var(--radius-sm)] px-1.5 py-1 text-left",
        tentative && "border border-dashed border-[var(--color-border-strong)]",
        cancelled && "opacity-50",
      )}
      style={{
        top,
        height,
        left: `calc(${leftPct}% + 1px)`,
        width: `calc(${widthPct}% - 2px)`,
        backgroundColor: `color-mix(in srgb, ${tintVar} 16%, var(--color-bg))`,
        borderLeft: `2px solid ${tintVar}`,
      }}
    >
      <span
        className={cn(
          "truncate text-[12px] font-medium leading-tight text-[var(--color-ink)]",
          cancelled && "line-through",
        )}
      >
        {event.title}
      </span>
      {height >= PXH ? (
        <span className="truncate text-[11px] leading-none tabular-nums text-[var(--color-ink-soft)]">
          {hhmm(new Date(event.start_at))}
        </span>
      ) : null}
    </button>
  );
}

type WeekGridProps = {
  days: Date[];
  events: AgendaEvent[];
  now: Date;
  onEventClick: (event: AgendaEvent) => void;
};

function WeekGrid({ days, events, now, onEventClick }: WeekGridProps) {
  const { minH, maxH } = hourBounds(events, days);
  const totalHeight = (maxH - minH) * PXH;
  const hours = Array.from({ length: maxH - minH + 1 }, (_, i) => minH + i);

  // Línea "ahora": solo si hoy cae en la semana mostrada y la hora está a la
  // vista. El dot va sobre la columna de hoy; la línea cruza las 7 columnas.
  const nh = nowHour();
  const todayIdx = days.findIndex((d) => isSameDay(d, now));
  const showNow = todayIdx >= 0 && nh >= minH && nh <= maxH;
  const nowTop = (nh - minH) * PXH;

  return (
    <div className="flex flex-col gap-2">
      {/* Cabecera: día abreviado + número (hoy resaltado) */}
      <div className="flex" style={{ paddingLeft: LEFT_GUTTER }} aria-hidden>
        {days.map((day) => {
          const today = isSameDay(day, now);
          return (
            <div key={day.toISOString()} className="flex flex-1 flex-col items-center gap-0.5">
              <span className="text-[12px] font-semibold uppercase text-[var(--color-ink-soft)]">
                {formatWeekdayShort(day)}
              </span>
              <span
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full text-[12px] font-semibold",
                  today
                    ? "bg-[var(--color-accent)] text-[var(--color-on-dark)]"
                    : "text-[var(--color-ink)]",
                )}
              >
                {formatDayNum(day)}
              </span>
            </div>
          );
        })}
      </div>

      {/* Grilla horaria */}
      <div className="relative flex" style={{ paddingLeft: LEFT_GUTTER, height: totalHeight }}>
        {/* Líneas horizontales + etiquetas de hora (label cada 2h, línea cada hora) */}
        {hours.map((h) => (
          <div
            key={h}
            aria-hidden
            className="pointer-events-none absolute inset-x-0"
            style={{ top: (h - minH) * PXH }}
          >
            {h % 2 === 0 ? (
              <span
                className="absolute right-full pr-1.5 text-[12px] font-semibold leading-none tabular-nums text-[var(--color-ink-soft)]"
                style={{ top: -6, width: LEFT_GUTTER }}
              >
                {h}
              </span>
            ) : null}
            <div
              className="absolute h-px"
              style={{ left: 0, right: 0, background: "var(--color-border)" }}
            />
          </div>
        ))}

        {/* Columnas de días */}
        {days.map((day, colIdx) => {
          const dayEvents = eventsForDay(events, day);
          // Columnas para los solapados de ESTE día (cada día es independiente).
          const placements = layoutColumns(dayEvents.map(toLayoutInterval));
          return (
            <div
              key={day.toISOString()}
              aria-hidden
              className={cn(
                "relative flex-1",
                colIdx > 0 && "border-l border-[var(--color-border)]",
              )}
            >
              {dayEvents.map((event) => (
                <ColEvent
                  key={event.id}
                  event={event}
                  minH={minH}
                  placement={placements.get(event.id) ?? { col: 0, cols: 1 }}
                  onEventClick={onEventClick}
                />
              ))}
            </div>
          );
        })}

        {/* Línea "ahora" */}
        {showNow ? (
          <div
            aria-hidden
            className="pointer-events-none absolute z-10"
            style={{ top: nowTop, left: LEFT_GUTTER, right: 0 }}
          >
            <span
              className="absolute -left-1 -top-[3px] h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: "var(--color-accent)" }}
            />
            <div className="h-0.5 w-full" style={{ backgroundColor: "var(--color-accent)" }} />
          </div>
        ) : null}
      </div>

      {/* Leyenda */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1" style={{ paddingLeft: LEFT_GUTTER }}>
        {(["estudio", "productividad", "bienestar", "vida"] as const).map((modeId) => {
          const mode = MODE_BY_ID[modeId];
          return (
            <span
              key={modeId}
              className="flex items-center gap-1.5 text-[12px] text-[var(--color-ink-soft)]"
            >
              <span
                aria-hidden
                className="inline-block h-2 w-3 rounded-[2px]"
                style={{
                  backgroundColor: `color-mix(in srgb, ${mode.tintVar} 16%, var(--color-bg))`,
                  borderLeft: `2px solid ${mode.tintVar}`,
                }}
              />
              {mode.label}
            </span>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Vista **semana** (desktop-only) — 7 columnas lun→dom, cabecera con el día de
 * hoy resaltado, grilla horaria con auto-fit del rango (incluye eventos fuera
 * de 8–20h en vez de descartarlos), bloques con título + hora, y línea de
 * "ahora". En mobile la Agenda usa Lista/Día (`AgendaView` no renderiza esta
 * vista en pantalla angosta): la grilla de 7 columnas no es legible bajo
 * ~360px y ninguna app de calendario líder la muestra en vertical.
 */
export function WeekView({ events, anchor, now, onEventClick }: Props) {
  const days = weekDays(anchor);

  return (
    <>
      {/* Alternativa accesible (C1): el grid visual es aria-hidden por ser una
          representación espacial que no linealiza; este resumen sr-only expone
          los mismos eventos (TODOS los del día, sin recorte horario) para
          lectores de pantalla, un ítem de lista por día. */}
      <ul className="sr-only" aria-label="Resumen de eventos de la semana">
        {days.map((day) => {
          const dayEvents = eventsForDay(events, day);
          return (
            <li key={day.toISOString()}>
              {formatDayLong(day)}
              {isSameDay(day, now) ? " (hoy)" : ""}:{" "}
              {dayEvents.length === 0
                ? "sin eventos"
                : dayEvents
                    .map(
                      (e) =>
                        `${e.title}, ${formatEventRange(e)}${
                          e.mode ? `, modo ${MODE_BY_ID[e.mode].label}` : ""
                        }${e.location ? `, en ${e.location}` : ""}${
                          e.status === "cancelled" ? ", cancelado" : ""
                        }`,
                    )
                    .join("; ")}
            </li>
          );
        })}
      </ul>

      <WeekGrid days={days} events={events} now={now} onEventClick={onEventClick} />
    </>
  );
}
