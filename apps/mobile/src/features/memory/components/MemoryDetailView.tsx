import { formatFullDate, presentDetail, type TimelineEntry } from "@ynara/core/features/memory";
import type { MemoryItemOut, MemoryLayer } from "@ynara/shared-schemas";
import type { ReactNode } from "react";
import { Text, View } from "react-native";
import { cn } from "@/lib/cn";
import { LAYER_BY_ID, LAYER_DOT_CLASS } from "../layers";
import { TimelineEntryRow } from "./TimelineEntryRow";

type Props = {
  layer: MemoryLayer;
  item: MemoryItemOut;
  related: TimelineEntry[];
  relatedPending: boolean;
  now: Date;
  /** Slot para las acciones (editar/borrar). */
  actions?: ReactNode;
};

/**
 * Detalle de un recuerdo (wireframe 20): capa, el recuerdo como quote, contexto,
 * meta, tags, acciones y relacionados. Espejo de `MemoryDetailView` de web, sin
 * el fondo `network` animado (flourishes diferidos). `presentDetail` (core)
 * resuelve quote/fecha/meta/tags/note por capa.
 */
export function MemoryDetailView({ layer, item, related, relatedPending, now, actions }: Props) {
  const layerInfo = LAYER_BY_ID[layer];
  const p = presentDetail(layer, item);

  return (
    <View className="gap-7">
      <View className="flex-row items-center gap-2 self-start rounded-pill border border-border bg-bg-soft px-3 py-1">
        <View className={cn("h-2 w-2 rounded-pill", LAYER_DOT_CLASS[layer])} />
        <Text className="text-caption text-ink-soft">{layerInfo.label}</Text>
      </View>

      <Text className="text-title text-ink-deep">{p.quote}</Text>

      {p.note ? (
        <Text className="border-l-2 border-border pl-4 text-body-sm text-ink-soft">{p.note}</Text>
      ) : null}

      {p.fromSession ? (
        <View className="gap-2">
          <Text className="text-caption text-ink-soft">Contexto</Text>
          <Text className="text-body text-ink-soft">
            Esto surgió en una conversación con Ynara.
          </Text>
        </View>
      ) : null}

      <View className="flex-row flex-wrap gap-x-10 gap-y-4">
        <View className="gap-1">
          <Text className="text-caption text-ink-soft">Fecha</Text>
          <Text className="text-body-sm text-ink">{formatFullDate(p.dateIso)}</Text>
        </View>
        {p.meta.map((row) => (
          <View key={row.label} className="gap-1">
            <Text className="text-caption text-ink-soft">{row.label}</Text>
            <Text className="text-body-sm text-ink">{row.value}</Text>
          </View>
        ))}
      </View>

      {p.tags.length > 0 ? (
        <View className="gap-3">
          <Text className="text-caption text-ink-soft">Detalles</Text>
          <View className="flex-row flex-wrap gap-2">
            {p.tags.map((tag) => (
              <View key={tag} className="rounded-pill border border-border bg-bg px-3 py-1">
                <Text className="text-body-sm text-ink-soft">{tag}</Text>
              </View>
            ))}
          </View>
        </View>
      ) : null}

      {actions ? <View className="flex-row flex-wrap gap-3">{actions}</View> : null}

      {p.fromSession ? (
        <View className="gap-3 border-t border-border pt-6">
          <Text className="text-caption text-ink-soft">Relacionado</Text>
          {relatedPending ? (
            <Text className="text-body-sm text-ink-soft">Buscando recuerdos cercanos…</Text>
          ) : related.length === 0 ? (
            <Text className="text-body-sm text-ink-soft">
              Nada más de esta conversación, por ahora.
            </Text>
          ) : (
            <View>
              {related.map((entry, index) => (
                <TimelineEntryRow
                  key={`${entry.layer}:${entry.ref}`}
                  entry={entry}
                  now={now}
                  first={index === 0}
                />
              ))}
            </View>
          )}
        </View>
      ) : null}
    </View>
  );
}
