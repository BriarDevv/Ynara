import { cn } from "@/lib/cn";
import type { AgendaEvent } from "../api";
import { eventsForDay, weekDays } from "../format";
import { formatDayNum, formatWeekdayShort, isSameDay } from "../labels";
import { EventBlock } from "./EventBlock";

type Props = {
  events: AgendaEvent[];
  /** Cualquier día de la semana a mostrar (se normaliza a lunes→domingo). */
  anchor: Date;
  /** Referencia de "ahora" para marcar el día de hoy. */
  now: Date;
};

/**
 * Vista **semana** (wireframe 11): las siete columnas lunes→domingo, cada una
 * con sus bloques. El día de hoy se resalta; los días libres muestran un guion
 * en vez de quedar vacíos.
 */
export function WeekView({ events, anchor, now }: Props) {
  const days = weekDays(anchor);

  return (
    <div className="flex flex-col gap-6">
      {days.map((day) => {
        const dayEvents = eventsForDay(events, day);
        const today = isSameDay(day, now);
        return (
          <section key={day.toISOString()} className="flex flex-col gap-3">
            <h3
              className={cn(
                "text-caption",
                today ? "text-[var(--color-ink)]" : "text-[var(--color-ink-soft)]",
              )}
            >
              {formatWeekdayShort(day)} {formatDayNum(day)}
              {today ? " · hoy" : ""}
            </h3>
            {dayEvents.length === 0 ? (
              <p className="pl-1 text-body-sm text-[var(--color-ink-faint)]">—</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {dayEvents.map((event, index) => (
                  <EventBlock key={event.id} event={event} index={index} />
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}
