import { groupByBucket, type TimelineFilter, useMemoryTimeline } from "@ynara/core/features/memory";
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, SectionList, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { ErrorCard } from "@/components/ui/ErrorCard";
import { LivingField } from "@/components/ui/LivingField";
import { Text } from "@/components/ui/Text";
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
 * cronológica agrupada por bucket temporal (Hoy / Esta semana / …). Con el fondo
 * vivo `network` (F3, Skia) detrás del contenido, teñido por el modo activo.
 *
 * La lista usa `SectionList` (virtualizada): monta solo las filas visibles, así
 * el timeline escala a muchos recuerdos sin renderizar todo de una. El header
 * (título + búsqueda + filtros) va en `ListHeaderComponent` y los estados sin
 * filas (cargando/error/vacío) en `ListEmptyComponent`.
 */
export function MemoriaScreen() {
  const router = useRouter();
  const [filter, setFilter] = useState<TimelineFilter>("all");
  const { data, isPending, isError, refetch, isFetching } = useMemoryTimeline(filter);

  // `now` estable durante la vida de la vista: ancla buckets y fechas relativas.
  const [now] = useState(() => new Date());
  const groups = useMemo(() => (data ? groupByBucket(data, now) : []), [data, now]);
  const sections = useMemo(
    () => groups.map((group) => ({ title: group.bucket, data: group.entries })),
    [groups],
  );

  // Header de la lista: scrollea con el contenido (no es sticky). El `pb-6`
  // reproduce el `gap-6` original entre los filtros y el primer bucket/estado.
  const header = (
    <View className="gap-6 pb-6">
      <View className="gap-2">
        <Text className="text-title font-display text-ink-deep">Memoria</Text>
        <Text className="text-body text-ink-soft">
          Todo lo que Ynara fue guardando con vos, en orden.
        </Text>
      </View>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Buscar en tu memoria"
        onPress={() => router.push("/buscar")}
        className="h-12 flex-row items-center rounded-lg border border-border bg-bg-soft px-4 active:opacity-70"
      >
        <Text className="flex-1 text-body text-ink-soft">Buscá en tu memoria…</Text>
      </Pressable>

      <ChipGroup
        label="Filtrar por tipo"
        options={FILTER_OPTIONS}
        value={filter}
        onChange={setFilter}
      />
    </View>
  );

  // Estados sin filas: cargando (skeleton), error (con reintento) o vacío.
  const empty = isPending ? (
    <MemoryTimelineSkeleton />
  ) : isError ? (
    <ErrorCard
      title="No pudimos traer tu memoria"
      hint="Puede ser un problema de conexión. Probá de nuevo."
      onRetry={() => refetch()}
      retrying={isFetching}
    />
  ) : (
    <View className="gap-1 rounded-lg border border-border bg-bg p-4">
      <Text className="text-body text-ink">Todavía no hay nada acá</Text>
      <Text className="text-body-sm text-ink-soft">
        A medida que charlen, Ynara va a ir recordando lo importante. Esto se llena solo.
      </Text>
    </View>
  );

  return (
    <View className="flex-1 bg-bg-canvas">
      <LivingField variant="network" />
      <SafeAreaView className="flex-1" edges={["top"]}>
        <SectionList
          className="flex-1"
          contentContainerClassName="px-6 py-8"
          sections={sections}
          keyExtractor={(item) => `${item.layer}:${item.ref}`}
          renderItem={({ item, index }) => (
            <TimelineEntryRow entry={item} now={now} first={index === 0} />
          )}
          renderSectionHeader={({ section }) => (
            <Text
              className={cn(
                "text-caption text-ink-soft pb-3",
                // `pt-8` entre grupos (= `gap-8`); el primer bucket no lo lleva
                // porque el `pb-6` del header ya da el aire.
                section.title !== sections[0]?.title && "pt-8",
              )}
            >
              {section.title}
            </Text>
          )}
          ListHeaderComponent={header}
          ListEmptyComponent={empty}
          stickySectionHeadersEnabled={false}
        />
      </SafeAreaView>
    </View>
  );
}
