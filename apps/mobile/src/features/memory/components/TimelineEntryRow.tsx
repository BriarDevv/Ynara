import { formatEntryDate, type TimelineEntry } from "@ynara/core/features/memory";
import { Text, View } from "react-native";
import { cn } from "@/lib/cn";
import { LAYER_BY_ID, LAYER_DOT_CLASS } from "../layers";

type Props = {
  entry: TimelineEntry;
  /** Referencia temporal para la meta relativa (inyectada para evitar drift). */
  now: Date;
  /** La primera fila no lleva borde superior (el separador va entre filas). */
  first: boolean;
};

/**
 * Una fila del timeline de memoria: dot de la capa + etiqueta + el recuerdo +
 * su fecha relativa. Espejo de `TimelineEntryRow` de web (sin el ícono de
 * `@ynara/ui` ni el link al detalle: navegar al detalle llega en el PR siguiente).
 * RN no soporta `divide-y` → separador con `border-t` por fila salvo la primera.
 */
export function TimelineEntryRow({ entry, now, first }: Props) {
  const layer = LAYER_BY_ID[entry.layer];
  return (
    <View className={cn("flex-row items-start gap-3 py-3.5", !first && "border-t border-border")}>
      <View className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-pill", LAYER_DOT_CLASS[entry.layer])} />
      <View className="min-w-0 flex-1 gap-1">
        <Text className="text-caption text-ink-soft">{layer.label}</Text>
        <Text className="text-body text-ink" numberOfLines={2}>
          {entry.title}
        </Text>
      </View>
      <Text className="mt-0.5 shrink-0 text-body-sm text-ink-soft">
        {formatEntryDate(entry.date, now)}
      </Text>
    </View>
  );
}
