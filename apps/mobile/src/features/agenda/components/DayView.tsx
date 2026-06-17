import type { AgendaEvent } from "@ynara/core/features/agenda";
import { Text, View } from "react-native";
import { eventsForDay } from "../format";
import { AgendaEventRow } from "./AgendaEventRow";

type Props = {
  events: AgendaEvent[];
  /** Día que se está mirando. */
  day: Date;
};

/**
 * Vista **día** (mobile): los bloques del día elegido, ordenados por hora.
 * Día libre → estado vacío en vez de una lista en blanco.
 * Espejo de `DayView` de web, adaptado a React Native / NativeWind.
 */
export function DayView({ events, day }: Props) {
  const dayEvents = eventsForDay(events, day);

  if (dayEvents.length === 0) {
    return (
      <View className="gap-1 rounded-lg border border-border bg-bg p-4">
        <Text className="text-body text-ink">Nada agendado este día</Text>
        <Text className="text-body-sm text-ink-soft">Tenés el día libre.</Text>
      </View>
    );
  }

  return (
    <View className="gap-3">
      {dayEvents.map((event) => (
        <AgendaEventRow key={event.id} event={event} />
      ))}
    </View>
  );
}
