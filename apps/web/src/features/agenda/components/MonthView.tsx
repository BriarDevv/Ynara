import { MODE_BY_ID } from "@/components/ui/modes";
import { cn } from "@/lib/cn";
import type { AgendaEvent } from "../api";
import { eventsForDay, monthGridDays } from "../format";
import { formatDayLong, formatDayNum, formatWeekdayShort, isSameDay, isSameMonth } from "../labels";

// Eventos mostrados por celda antes de colapsar el resto en "+N más".
const MAX_VISIBLE = 3;

type Props = {
  events: AgendaEvent[];
  /** Cualquier día del mes a mostrar (se normaliza a la grilla de 6 semanas). */
  anchor: Date;
  /** Referencia de "ahora" para marcar el día de hoy. */
  now: Date;
  /** Al tocar un día, saltar a la vista Día de esa fecha. */
  onSelectDay: (day: Date) => void;
};

type DayCellProps = {
  day: Date;
  events: AgendaEvent[];
  inMonth: boolean;
  isToday: boolean;
  onSelect: (day: Date) => void;
};

/**
 * Celda de día = **botón** con nombre accesible ("Martes 7 de mayo, 3 eventos").
 * Los eventos de adentro son decorativos (`aria-hidden`): el resumen lo da el
 * `aria-label`. Tocar la celda salta a la vista Día (`onSelect`). Accesible por
 * teclado (Tab + Enter), sin el `role=grid` completo (research §2.4).
 */
function DayCell({ day, events, inMonth, isToday, onSelect }: DayCellProps) {
  const dayEvents = eventsForDay(events, day);
  const visible = dayEvents.slice(0, MAX_VISIBLE);
  const extra = dayEvents.length - visible.length;

  const count = dayEvents.length;
  const countLabel = count === 0 ? "sin eventos" : `${count} ${count === 1 ? "evento" : "eventos"}`;

  return (
    <button
      type="button"
      onClick={() => onSelect(day)}
      aria-label={`${formatDayLong(day)}, ${countLabel}`}
      className={cn(
        "flex min-h-[84px] flex-col gap-1 rounded-[var(--radius-md)] border border-transparent p-1.5 text-left",
        "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
        "hover:border-[var(--color-border)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-selected-ring)] md:min-h-[104px]",
        !inMonth && "opacity-40",
      )}
    >
      {/* Número de día (hoy = círculo de acento) */}
      <span aria-hidden className="flex">
        <span
          className={cn(
            "flex h-6 w-6 items-center justify-center rounded-full text-[12px] font-semibold tabular-nums",
            isToday
              ? "bg-[var(--color-accent)] text-[var(--color-on-dark)]"
              : "text-[var(--color-ink)]",
          )}
        >
          {formatDayNum(day)}
        </span>
      </span>

      {/* Eventos (decorativos; el aria-label de la celda los resume) */}
      <span aria-hidden className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-hidden">
        {visible.map((event) => {
          const tintVar = event.mode
            ? MODE_BY_ID[event.mode].tintVar
            : "var(--color-border-strong)";
          return (
            <span
              key={event.id}
              className={cn(
                "truncate rounded-[3px] px-1 text-[10px] leading-tight text-[var(--color-ink)]",
                event.status === "cancelled" && "line-through opacity-60",
              )}
              style={{
                // 16% = mismo tint que Day/Week (una sola fuente del valor).
                backgroundColor: `color-mix(in srgb, ${tintVar} 16%, var(--color-bg))`,
                // Spine dashed para tentative (paridad de estado con Day/Week).
                borderLeft: `2px ${event.status === "tentative" ? "dashed" : "solid"} ${tintVar}`,
              }}
            >
              {event.title}
            </span>
          );
        })}
        {extra > 0 ? (
          <span className="px-1 text-[10px] font-medium text-[var(--color-ink-soft)]">
            +{extra} más
          </span>
        ) : null}
      </span>
    </button>
  );
}

/**
 * Vista **mes** — grilla de celdas 6×7 (6 semanas fijas, lun→domingo). Cada día
 * es un botón que salta a la vista Día; los días fuera del mes van atenuados,
 * hoy con círculo de acento. Componente aparte del time-grid de Día/Semana
 * (render distinto, CALENDAR-RESEARCH-2026 §2.1).
 */
export function MonthView({ events, anchor, now, onSelectDay }: Props) {
  const days = monthGridDays(anchor);
  const weekdayHeaders = days.slice(0, 7);

  return (
    <div className="flex flex-col gap-2">
      {/* Cabecera de días de la semana (decorativa: cada celda lleva su nombre
          completo en el aria-label). */}
      <div aria-hidden className="grid grid-cols-7 gap-1">
        {weekdayHeaders.map((d) => (
          <span
            key={d.toISOString()}
            className="text-center text-[12px] font-semibold uppercase text-[var(--color-ink-soft)]"
          >
            {formatWeekdayShort(d)}
          </span>
        ))}
      </div>

      {/* Grilla 6×7 */}
      <div className="grid grid-cols-7 gap-1">
        {days.map((day) => (
          <DayCell
            key={day.toISOString()}
            day={day}
            events={events}
            inMonth={isSameMonth(day, anchor)}
            isToday={isSameDay(day, now)}
            onSelect={onSelectDay}
          />
        ))}
      </div>
    </div>
  );
}
