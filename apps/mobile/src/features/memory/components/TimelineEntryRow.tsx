import { formatEntryDate, type TimelineEntry } from "@ynara/core/features/memory";
import { useRouter } from "expo-router";
import { Pressable, View } from "react-native";
import { Text } from "@/components/ui/Text";
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
 * su fecha relativa. **Tappable** → abre el detalle (`/memoria/[ref]?capa=`): la
 * capa viaja por query porque la ruta `[ref]` es de un solo segmento y el
 * detalle del backend necesita `{layer}/{ref}`. RN no soporta `divide-y` → el
 * separador es un `border-t` por fila salvo la primera.
 */
export function TimelineEntryRow({ entry, now, first }: Props) {
  const router = useRouter();
  const layer = LAYER_BY_ID[entry.layer];
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${layer.label}: ${entry.title}`}
      onPress={() =>
        router.push({ pathname: "/memoria/[ref]", params: { ref: entry.ref, capa: entry.layer } })
      }
      className={cn(
        "flex-row items-start gap-3 py-3.5 active:opacity-60",
        !first && "border-t border-border",
      )}
    >
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
      <Text className="mt-0.5 shrink-0 text-body text-ink-faint">›</Text>
    </Pressable>
  );
}
