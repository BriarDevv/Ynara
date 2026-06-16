import type { Task } from "@ynara/shared-schemas";
import { Pressable, Text, View } from "react-native";
import { cn } from "@/lib/cn";
import { formatTaskMeta } from "../format";

type Props = {
  task: Task;
  onToggle: (task: Task) => void;
  /** La primera fila no lleva borde superior (el separador va entre filas). */
  first: boolean;
};

/**
 * Una prioridad del día (wireframe 06): el check a la izquierda (toggle
 * pending↔done) + el título + la meta "14:00 · 45 min" / "09:15 · completada".
 * Hecha → título atenuado. El check es accesible (role checkbox + estado); el
 * toggle es optimista (lo maneja el hook en la sección). RN no soporta
 * `divide-y`, así que el separador es un `border-t` por fila salvo la primera.
 */
export function PriorityRow({ task, onToggle, first }: Props) {
  const done = task.status === "done";
  const meta = formatTaskMeta(task);
  return (
    <View className={cn("flex-row items-start gap-3 py-3.5", !first && "border-t border-border")}>
      <Pressable
        accessibilityRole="checkbox"
        accessibilityState={{ checked: done }}
        accessibilityLabel={
          done ? `Marcar "${task.title}" como pendiente` : `Marcar "${task.title}" como hecha`
        }
        onPress={() => onToggle(task)}
        hitSlop={8}
        className={cn(
          "mt-0.5 h-6 w-6 items-center justify-center rounded-pill border-2",
          done ? "border-ink bg-ink" : "border-border-strong bg-transparent",
        )}
      >
        {done ? <View className="h-2 w-2 rounded-pill bg-bg" /> : null}
      </Pressable>
      <View className="flex-1 gap-1">
        <Text className={cn("text-body", done ? "text-ink-soft" : "text-ink")}>{task.title}</Text>
        {meta ? <Text className="text-body-sm text-ink-soft">{meta}</Text> : null}
      </View>
    </View>
  );
}
