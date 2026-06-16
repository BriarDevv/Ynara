import { groupByBucket, type TimelineFilter, useMemoryTimeline } from "@ynara/core/features/memory";
import { useMemo, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { cn } from "@/lib/cn";
import { MemoryTimelineSkeleton } from "./components/MemoryTimelineSkeleton";
import { TimelineEntryRow } from "./components/TimelineEntryRow";

const FILTER_OPTIONS = [
  { value: "all", label: "Todo" },
  { value: "semantic", label: "Hechos" },
  { value: "episodic", label: "Momentos" },
  { value: "procedural", label: "Costumbres" },
] as const satisfies readonly { value: TimelineFilter; label: string }[];

/**
 * Pantalla **Memoria** (timeline, wireframe 17) — espejo de `MemoryView` de web.
 * Conecta a `GET /v1/memory` (mock-first) vía `useMemoryTimeline` y resuelve los
 * 4 estados: cargando (skeleton), error (con reintento), vacío y la lista
 * cronológica agrupada por bucket temporal (Hoy / Esta semana / …). Sin el fondo
 * `network` animado de web (flourishes diferidos). El detalle del recuerdo llega
 * en el PR siguiente.
 */
export function MemoriaScreen() {
  const [filter, setFilter] = useState<TimelineFilter>("all");
  const { data, isPending, isError, refetch, isFetching } = useMemoryTimeline(filter);

  // `now` estable durante la vida de la vista: ancla buckets y fechas relativas.
  const [now] = useState(() => new Date());
  const groups = useMemo(() => (data ? groupByBucket(data, now) : []), [data, now]);

  return (
    <SafeAreaView className="flex-1 bg-bg-canvas" edges={["top"]}>
      <ScrollView contentContainerClassName="gap-6 px-6 py-8">
        <View className="gap-2">
          <Text className="text-title font-semibold text-ink-deep">Memoria</Text>
          <Text className="text-body text-ink-soft">
            Todo lo que Ynara fue guardando con vos, en orden.
          </Text>
        </View>

        <ChipGroup
          label="Filtrar por tipo"
          options={FILTER_OPTIONS}
          value={filter}
          onChange={setFilter}
        />

        {isPending ? (
          <MemoryTimelineSkeleton />
        ) : isError ? (
          <View className="gap-2 rounded-lg border border-border bg-bg p-4">
            <Text className="text-body text-ink">No pudimos traer tu memoria</Text>
            <Text className="text-body-sm text-ink-soft">
              Puede ser un problema de conexión. Probá de nuevo.
            </Text>
            <Pressable onPress={() => refetch()} disabled={isFetching} hitSlop={8}>
              <Text className={cn("text-button text-ink underline", isFetching && "opacity-50")}>
                Reintentar
              </Text>
            </Pressable>
          </View>
        ) : groups.length === 0 ? (
          <View className="gap-1 rounded-lg border border-border bg-bg p-4">
            <Text className="text-body text-ink">Todavía no hay nada acá</Text>
            <Text className="text-body-sm text-ink-soft">
              A medida que charlen, Ynara va a ir recordando lo importante. Esto se llena solo.
            </Text>
          </View>
        ) : (
          <View className="gap-8">
            {groups.map((group) => (
              <View key={group.bucket} className="gap-3">
                <Text className="text-caption text-ink-soft">{group.bucket}</Text>
                <View>
                  {group.entries.map((entry, index) => (
                    <TimelineEntryRow
                      key={`${entry.layer}:${entry.ref}`}
                      entry={entry}
                      now={now}
                      first={index === 0}
                    />
                  ))}
                </View>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
