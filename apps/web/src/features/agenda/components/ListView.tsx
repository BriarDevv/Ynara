import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { MODE_BY_ID } from "@/components/ui/modes";
import { cn } from "@/lib/cn";
import type { AgendaEvent } from "../api";
import { eventsForDay, weekDays } from "../format";
import { formatDayLong, formatWeekdayShort, isSameDay } from "../labels";

type Props = {
  events: AgendaEvent[];
  /** Referencia de "ahora" para agrupar Hoy / Mañana / Esta semana. */
  now: Date;
  /** Tocar una fila abre el sheet de edición de ese evento. */
  onEventClick: (event: AgendaEvent) => void;
};

type Grupo = {
  label: string;
  events: AgendaEvent[];
};

/** Agrupa los eventos de la semana en Hoy / Mañana / Esta semana. */
function buildGroups(events: AgendaEvent[], now: Date): Grupo[] {
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);

  const days = weekDays(now);

  const hoy = eventsForDay(events, now);
  const manana = eventsForDay(events, tomorrow);

  // Resto de la semana (sin hoy ni mañana)
  const semanaEvents: AgendaEvent[] = [];
  for (const day of days) {
    if (isSameDay(day, now) || isSameDay(day, tomorrow)) continue;
    semanaEvents.push(...eventsForDay(events, day));
  }
  semanaEvents.sort((a, b) => a.start_at.localeCompare(b.start_at));

  return [
    { label: "Hoy", events: hoy },
    { label: "Mañana", events: manana },
    { label: "Esta semana", events: semanaEvents },
  ].filter((g) => g.events.length > 0);
}

/** Etiqueta de sección aireada (caption uppercase, ink-soft). */
function SectionLabel({ children }: { children: string }) {
  return (
    <p className="text-caption uppercase tracking-widest text-[var(--color-ink-soft)]">
      {children}
    </p>
  );
}

type RowProps = {
  event: AgendaEvent;
  now: Date;
  onEventClick: (event: AgendaEvent) => void;
};

/** Fila de evento aireada (botón): sin caja, separada por hairline. Tocarla
 *  abre el sheet de edición. Es la vía accesible por teclado de la Agenda. */
function EventRow({ event, now: _now, onEventClick }: RowProps) {
  const start = new Date(event.start_at);
  const end = new Date(start.getTime() + event.duration_min * 60_000);
  const hhmm = (d: Date) =>
    `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  const range = `${hhmm(start)} – ${hhmm(end)}`;

  const tintVar = event.mode ? MODE_BY_ID[event.mode].tintVar : "var(--color-border-strong)";
  const cancelled = event.status === "cancelled";

  // Etiqueta legible del día (para "Esta semana" donde el día es relevante)
  const dayLabel = formatWeekdayShort(start);
  const dayNum = start.getDate();
  const longLabel = formatDayLong(start);

  return (
    <li
      className={cn(
        "border-b border-[var(--color-border)] last:border-b-0",
        cancelled && "opacity-50",
      )}
    >
      <button
        type="button"
        onClick={() => onEventClick(event)}
        title={longLabel}
        aria-label={`Editar ${event.title}`}
        className="flex w-full items-start gap-3 rounded-[var(--radius-sm)] py-3.5 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-selected-ring)]"
      >
        {/* Dot de modo */}
        <span
          aria-hidden
          className="mt-[5px] h-2 w-2 shrink-0 rounded-full"
          style={{ backgroundColor: tintVar }}
        />

        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          {/* Día breve (lunes 7) */}
          <span className="text-caption text-[var(--color-ink-soft)]">
            {dayLabel} {dayNum}
          </span>
          {/* Título */}
          <span className={cn("text-body text-[var(--color-ink)]", cancelled && "line-through")}>
            {event.title}
          </span>
          {/* Lugar */}
          {event.location ? (
            <span className="text-body-sm text-[var(--color-ink-soft)]">{event.location}</span>
          ) : null}
        </div>

        {/* Rango horario al borde derecho */}
        <span className="shrink-0 text-body-sm tabular-nums text-[var(--color-ink-soft)]">
          {range}
        </span>
      </button>
    </li>
  );
}

/**
 * Vista **lista** de la Agenda: eventos agrupados por día relativo
 * (Hoy / Mañana / Esta semana), filas aireadas sin caja.
 */
export function ListView({ events, now, onEventClick }: Props) {
  const groups = buildGroups(events, now);

  if (groups.length === 0) {
    return <EmptyStateCard title="Nada en la semana" hint="Tenés la semana libre." />;
  }

  return (
    <div className="flex flex-col gap-8">
      {groups.map((g) => (
        <section key={g.label} className="flex flex-col gap-3">
          <SectionLabel>{g.label}</SectionLabel>
          <ul aria-label={g.label}>
            {g.events.map((e) => (
              <EventRow key={e.id} event={e} now={now} onEventClick={onEventClick} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
