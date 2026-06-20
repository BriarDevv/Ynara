import { useEvents } from "@ynara/core/features/agenda";
import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { ErrorCard } from "@/components/ui/ErrorCard";
import { LivingField } from "@/components/ui/LivingField";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";
import { AgendaSkeleton } from "./components/AgendaSkeleton";
import { DayView } from "./components/DayView";
import { WeekView } from "./components/WeekView";
import { formatDayLong, formatWeekRange, isSameDay, startOfWeek } from "./format";

type ViewMode = "dia" | "semana";

const VIEW_OPTIONS = [
  { value: "dia", label: "Día" },
  { value: "semana", label: "Semana" },
] as const satisfies readonly { value: ViewMode; label: string }[];

/**
 * Pantalla **Agenda** (mobile) — espejo de `AgendaView` de web (wireframes 10/11):
 * toggle día↔semana + navegación anterior/hoy/siguiente + 4 estados
 * (cargando/error/vacío/datos). Default semana para no arrancar en un día vacío.
 *
 * `now` se fija una vez por montaje para anclar "hoy" sin drift; `anchor` es
 * el día/semana en foco, que la navegación desplaza.
 */
export function AgendaScreen() {
  const [now] = useState(() => new Date());
  const [view, setView] = useState<ViewMode>("semana");
  const [anchor, setAnchor] = useState<Date>(() => new Date());

  const { data, isPending, isError, refetch, isFetching } = useEvents();

  const stepDays = view === "dia" ? 1 : 7;
  const shift = (direction: -1 | 1) => {
    setAnchor((prev) => {
      const next = new Date(prev);
      next.setDate(next.getDate() + direction * stepDays);
      return next;
    });
  };

  const periodLabel = view === "dia" ? formatDayLong(anchor) : formatWeekRange(startOfWeek(anchor));

  const onNow =
    view === "dia" ? isSameDay(anchor, now) : isSameDay(startOfWeek(anchor), startOfWeek(now));

  return (
    <View className="flex-1 bg-bg-canvas">
      <LivingField variant="aurora" />
      <SafeAreaView className="flex-1" edges={["top"]}>
        <ScrollView contentContainerClassName="gap-8 px-6 py-8">
          {/* Header */}
          <View className="gap-4">
            <View className="flex-row items-center justify-between gap-3">
              <Text className="text-title font-display text-ink">Agenda</Text>
              <ChipGroup options={VIEW_OPTIONS} value={view} onChange={(v) => setView(v)} />
            </View>

            <Text className="text-body text-ink-soft">{periodLabel}</Text>

            {/* Navegación anterior / hoy / siguiente */}
            <View className="flex-row items-center gap-2">
              <Pressable
                onPress={() => shift(-1)}
                accessibilityLabel={view === "dia" ? "Día anterior" : "Semana anterior"}
                hitSlop={8}
                className="h-9 w-9 items-center justify-center rounded-full border border-border"
              >
                <Text className="text-body text-ink-soft">‹</Text>
              </Pressable>

              <Pressable
                onPress={() => setAnchor(new Date())}
                disabled={onNow}
                hitSlop={8}
                className={cn("rounded-pill px-4 py-2", onNow && "opacity-40")}
              >
                <Text className="text-button text-ink-soft">Hoy</Text>
              </Pressable>

              <Pressable
                onPress={() => shift(1)}
                accessibilityLabel={view === "dia" ? "Día siguiente" : "Semana siguiente"}
                hitSlop={8}
                className="h-9 w-9 items-center justify-center rounded-full border border-border"
              >
                <Text className="text-body text-ink-soft">›</Text>
              </Pressable>
            </View>
          </View>

          {/* Contenido: 4 estados */}
          {isPending ? (
            <AgendaSkeleton />
          ) : isError ? (
            <ErrorCard
              title="No pudimos traer tu agenda"
              hint="Puede ser un problema de conexión. Probá de nuevo."
              onRetry={() => refetch()}
              retrying={isFetching}
            />
          ) : view === "dia" ? (
            <DayView events={data} day={anchor} />
          ) : (
            <WeekView events={data} anchor={anchor} now={now} />
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
