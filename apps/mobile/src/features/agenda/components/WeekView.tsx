import type { AgendaEvent } from "@ynara/core/features/agenda";
import { View } from "react-native";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";
import { eventsForDay, formatDayNum, formatWeekdayShort, isSameDay, weekDays } from "../format";
import { AgendaEventRow } from "./AgendaEventRow";

type Props = {
  events: AgendaEvent[];
  /** Cualquier día de la semana a mostrar (se normaliza a lunes→domingo). */
  anchor: Date;
  /** Referencia de "ahora" para marcar el día de hoy. */
  now: Date;
};

/**
 * Vista **semana** (mobile): los siete días lun→dom, cada uno con sus bloques.
 * El día de hoy se resalta; los días libres muestran un guion en vez de
 * quedar vacíos. Espejo de `WeekView` de web, adaptado a React Native / NativeWind.
 */
export function WeekView({ events, anchor, now }: Props) {
  const days = weekDays(anchor);

  return (
    <View className="gap-6">
      {days.map((day) => {
        const dayEvents = eventsForDay(events, day);
        const today = isSameDay(day, now);
        return (
          <View key={day.toISOString()} className="gap-3">
            {/* Cabecera de día */}
            <Text className={cn("text-caption", today ? "text-ink" : "text-ink-soft")}>
              {formatWeekdayShort(day)} {formatDayNum(day)}
              {today ? " · hoy" : ""}
            </Text>

            {dayEvents.length === 0 ? (
              <Text className="pl-1 text-body-sm text-ink-faint">—</Text>
            ) : (
              <View className="gap-2">
                {dayEvents.map((event) => (
                  <AgendaEventRow key={event.id} event={event} />
                ))}
              </View>
            )}
          </View>
        );
      })}
    </View>
  );
}
