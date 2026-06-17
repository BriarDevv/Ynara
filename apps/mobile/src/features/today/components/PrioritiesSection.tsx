import { useTasks, useToggleTask } from "@ynara/core/features/today";
import { Pressable, View } from "react-native";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";
import { PrioritiesSkeleton } from "./PrioritiesSkeleton";
import { PriorityRow } from "./PriorityRow";

/**
 * Sección **Prioridades del día** (wireframe 06). Conecta a `GET /v1/tasks`
 * (mock) vía `useTasks` y resuelve los 4 estados: cargando (skeleton), error
 * (con reintento), vacío (hint compacto) y la lista con el check optimista
 * (`useToggleTask`). Espejo de la sección de web.
 */
export function PrioritiesSection() {
  const { data, isPending, isError, refetch, isFetching } = useTasks();
  const toggle = useToggleTask();

  return (
    <View className="gap-3">
      <Text className="text-caption text-ink-soft">Prioridades del día</Text>

      {isPending ? (
        <PrioritiesSkeleton />
      ) : isError ? (
        <View className="gap-2 rounded-lg border border-border bg-bg p-4">
          <Text className="text-body text-ink">No pudimos traer tus prioridades</Text>
          <Text className="text-body-sm text-ink-soft">
            Puede ser un problema de conexión. Probá de nuevo.
          </Text>
          <Pressable onPress={() => refetch()} disabled={isFetching} hitSlop={8}>
            <Text className={cn("text-button text-ink underline", isFetching && "opacity-50")}>
              Reintentar
            </Text>
          </Pressable>
        </View>
      ) : data.length === 0 ? (
        <View className="gap-1 rounded-lg border border-border bg-bg p-4">
          <Text className="text-body text-ink">Sin urgentes esta hora</Text>
          <Text className="text-body-sm text-ink-soft">
            Aprovechá el tiempo libre, o pedile algo a Ynara.
          </Text>
        </View>
      ) : (
        <View>
          {data.map((task, index) => (
            <PriorityRow key={task.id} task={task} first={index === 0} onToggle={toggle.mutate} />
          ))}
        </View>
      )}
    </View>
  );
}
