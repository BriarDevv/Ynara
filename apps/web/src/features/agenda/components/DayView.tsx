import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import type { AgendaEvent } from "../api";
import { eventsForDay } from "../format";
import { EventBlock } from "./EventBlock";

type Props = {
  events: AgendaEvent[];
  /** Día que se está mirando. */
  day: Date;
};

/**
 * Vista **día** (wireframe 10): los bloques del día elegido, ordenados por hora.
 * Día libre → estado vacío en vez de una lista en blanco.
 */
export function DayView({ events, day }: Props) {
  const dayEvents = eventsForDay(events, day);

  if (dayEvents.length === 0) {
    return <EmptyStateCard title="Nada agendado este día" hint="Tenés el día libre." />;
  }

  return (
    <ul className="flex flex-col gap-3">
      {dayEvents.map((event, index) => (
        <EventBlock key={event.id} event={event} index={index} />
      ))}
    </ul>
  );
}
