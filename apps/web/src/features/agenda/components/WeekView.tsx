import { MODE_BY_ID } from "@/components/ui/modes";
import { cn } from "@/lib/cn";
import type { AgendaEvent } from "../api";
import { eventsForDay, gridHeight, gridTop, isInRange, weekDays } from "../format";
import { formatDayNum, formatWeekdayShort, isSameDay } from "../labels";

// ── Constantes de la grilla ─────────────────────────────────────────────────
const H0 = 8;
const H1 = 20;
// Marcas de hora para el eje vertical (cada 2h para no saturar)
const HOUR_MARKS = [8, 10, 12, 14, 16, 18, 20];

// px por hora según breakpoint
const PXH_DESKTOP = 20;
const PXH_MOBILE = 14; // más compacto en mobile

const LEFT_GUTTER = 22; // ancho de la columna de horas (px)

type Props = {
  events: AgendaEvent[];
  /** Cualquier día de la semana a mostrar (se normaliza a lunes→domingo). */
  anchor: Date;
  /** Referencia de "ahora" para marcar el día de hoy. */
  now: Date;
};

type ColEventProps = {
  event: AgendaEvent;
  pxh: number;
};

/** Barra de evento posicionada absolute dentro de su columna. */
function ColEvent({ event, pxh }: ColEventProps) {
  const tintVar = event.mode ? MODE_BY_ID[event.mode].tintVar : "var(--color-border-strong)";
  const cancelled = event.status === "cancelled";
  const top = gridTop(event, H0, pxh);
  const height = gridHeight(event, pxh, 4);

  return (
    <div
      title={event.title}
      aria-hidden
      className={cn("absolute inset-x-[2px] rounded-[var(--radius-sm)]", cancelled && "opacity-40")}
      style={{
        top,
        height,
        backgroundColor: `color-mix(in srgb, ${tintVar} 40%, var(--color-bg))`,
        borderLeft: `2px solid ${tintVar}`,
      }}
    />
  );
}

type WeekGridProps = {
  days: Date[];
  events: AgendaEvent[];
  now: Date;
  pxh: number;
};

function WeekGrid({ days, events, now, pxh }: WeekGridProps) {
  const totalHeight = (H1 - H0) * pxh;

  return (
    <div className="flex flex-col gap-2">
      {/* Cabecera: día abreviado + número (hoy resaltado) */}
      <div className="flex" style={{ paddingLeft: LEFT_GUTTER }} aria-hidden>
        {days.map((day) => {
          const today = isSameDay(day, now);
          return (
            <div key={day.toISOString()} className="flex flex-1 flex-col items-center gap-0.5">
              <span className="text-[10px] font-semibold uppercase text-[var(--color-ink-faint)]">
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
        {/* Etiquetas de hora + líneas horizontales */}
        {HOUR_MARKS.map((h) => (
          <div
            key={h}
            aria-hidden
            className="pointer-events-none absolute inset-x-0"
            style={{ top: (h - H0) * pxh }}
          >
            <span
              className="absolute right-full pr-1 text-[9px] font-semibold leading-none tabular-nums text-[var(--color-ink-faint)]"
              style={{ top: -6, width: LEFT_GUTTER }}
            >
              {h}
            </span>
            <div
              className="absolute h-px"
              style={{ left: 0, right: 0, background: "var(--color-border)" }}
            />
          </div>
        ))}

        {/* Columnas de días */}
        {days.map((day, colIdx) => {
          const dayEvents = eventsForDay(events, day).filter((e) => isInRange(e, H0, H1));
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
                <ColEvent key={event.id} event={event} pxh={pxh} />
              ))}
            </div>
          );
        })}
      </div>

      {/* Leyenda */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1" style={{ paddingLeft: LEFT_GUTTER }}>
        {(["estudio", "productividad", "bienestar", "vida"] as const).map((modeId) => {
          const mode = MODE_BY_ID[modeId];
          return (
            <span
              key={modeId}
              className="flex items-center gap-1.5 text-[11px] text-[var(--color-ink-soft)]"
            >
              <span
                aria-hidden
                className="inline-block h-2 w-3 rounded-[2px]"
                style={{
                  backgroundColor: `color-mix(in srgb, ${mode.tintVar} 40%, var(--color-bg))`,
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
 * Vista **semana** — 7 columnas lun→dom, cabecera con día resaltado (hoy
 * lleva círculo del acento), grilla horaria de fondo, eventos como barras
 * teñidas por modo. Responsive: más compacta en mobile (14 px/h vs 20 px/h),
 * scroll horizontal habilitado para que no se rompa en pantalla angosta.
 */
export function WeekView({ events, anchor, now }: Props) {
  const days = weekDays(anchor);

  return (
    <>
      {/* Mobile: PXH menor, scroll horizontal si hace falta */}
      <div className="overflow-x-auto md:hidden">
        <div className="min-w-[320px]">
          <WeekGrid days={days} events={events} now={now} pxh={PXH_MOBILE} />
        </div>
      </div>
      {/* Desktop */}
      <div className="hidden md:block">
        <WeekGrid days={days} events={events} now={now} pxh={PXH_DESKTOP} />
      </div>
    </>
  );
}
