import { formatEntryDate } from "@ynara/core/features/memory";
import type { MemorySearchHit } from "@ynara/shared-schemas";
import { useRouter } from "expo-router";
import { Pressable, Text, View } from "react-native";
import { cn } from "@/lib/cn";
import { LAYER_BY_ID, LAYER_DOT_CLASS } from "../layers";

type Props = {
  hit: MemorySearchHit;
  /** Referencia temporal para la fecha relativa (inyectada para evitar drift). */
  now: Date;
  /** La primera fila no lleva borde superior (el separador va entre filas). */
  first: boolean;
};

/**
 * Una fila de resultado de búsqueda: dot de la capa + etiqueta + el fragmento
 * que matcheó + su fecha (si la hay). **Tappable** → abre el detalle
 * (`/memoria/[ref]?capa=`), igual que el timeline. Misma forma visual que
 * `TimelineEntryRow` pero sobre un `MemorySearchHit`; espeja el `SearchResultRow`
 * de web (sin Icon: mobile distingue la capa por dot).
 */
export function SearchResultRow({ hit, now, first }: Props) {
  const router = useRouter();
  const layer = LAYER_BY_ID[hit.layer];
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${layer.label}: ${hit.snippet}`}
      onPress={() =>
        router.push({ pathname: "/memoria/[ref]", params: { ref: hit.ref, capa: hit.layer } })
      }
      className={cn(
        "flex-row items-start gap-3 py-3.5 active:opacity-60",
        !first && "border-t border-border",
      )}
    >
      <View className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-pill", LAYER_DOT_CLASS[hit.layer])} />
      <View className="min-w-0 flex-1 gap-1">
        <Text className="text-caption text-ink-soft">{layer.label}</Text>
        <Text className="text-body text-ink" numberOfLines={2}>
          {hit.snippet}
        </Text>
      </View>
      {hit.occurred_at ? (
        <Text className="mt-0.5 shrink-0 text-body-sm text-ink-soft">
          {formatEntryDate(hit.occurred_at, now)}
        </Text>
      ) : null}
      <Text className="mt-0.5 shrink-0 text-body text-ink-faint">›</Text>
    </Pressable>
  );
}
