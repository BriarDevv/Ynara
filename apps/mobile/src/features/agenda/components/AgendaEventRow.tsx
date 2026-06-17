import type { AgendaEvent } from "@ynara/core/features/agenda";
import { Text, View } from "react-native";
import { MODE_DOT_CLASS } from "@/components/ui/modes";
import { cn } from "@/lib/cn";
import { formatEventRange } from "../format";

/** Etiqueta del estado no-confirmado (el confirmado no lleva tag). */
const STATUS_LABEL: Record<"tentative" | "cancelled", string> = {
  tentative: "Tentativo",
  cancelled: "Cancelado",
};

/**
 * Color del spine lateral por modo. Mapa estático (NativeWind no puede
 * interpolar `bg-mode-${id}` en runtime). Espeja `EventBlock` de web.
 */
const MODE_SPINE_COLOR: Record<string, string> = {
  productividad: "#4f7fd4",
  estudio: "#7c6fd4",
  bienestar: "#4fbf8a",
  vida: "#d47c4f",
  memoria: "#d4b74f",
};

type Props = {
  event: AgendaEvent;
};

/**
 * Un bloque de la Agenda (mobile): rango horario derivado + título + lugar
 * opcional, con spine a la izquierda teñido por el modo del evento.
 * `tentative` → borde punteado + tag; `cancelled` → título tachado + atenuado.
 * Espejo de `EventBlock` (web), adaptado a React Native / NativeWind.
 */
export function AgendaEventRow({ event }: Props) {
  const spineColor = event.mode ? (MODE_SPINE_COLOR[event.mode] ?? "#9ca3af") : "#9ca3af";
  const cancelled = event.status === "cancelled";
  const tentative = event.status === "tentative";

  return (
    <View
      className={cn(
        "flex-row gap-3 rounded-lg border bg-bg p-4",
        tentative ? "border-dashed border-border-strong" : "border-border",
        cancelled && "opacity-60",
      )}
    >
      {/* Spine lateral teñido por modo */}
      <View
        style={{ width: 4, borderRadius: 99, backgroundColor: spineColor }}
        className="self-stretch"
      />

      <View className="min-w-0 flex-1 gap-1">
        {/* Rango horario */}
        <Text className="text-body-sm tabular-nums text-ink-soft">{formatEventRange(event)}</Text>

        {/* Título */}
        <Text
          className={cn("text-body", cancelled ? "text-ink-soft line-through" : "text-ink")}
          numberOfLines={2}
        >
          {event.title}
        </Text>

        {/* Lugar opcional */}
        {event.location ? (
          <Text className="text-body-sm text-ink-soft" numberOfLines={1}>
            {event.location}
          </Text>
        ) : null}

        {/* Tag tentativo / cancelado */}
        {event.status !== "confirmed" ? (
          <Text className="text-caption text-ink-soft">{STATUS_LABEL[event.status]}</Text>
        ) : null}

        {/* Dot de modo (debajo del lugar, si tiene modo) */}
        {event.mode ? (
          <View className="flex-row items-center gap-1.5 pt-0.5">
            <View className={cn("h-2 w-2 rounded-pill", MODE_DOT_CLASS[event.mode])} />
          </View>
        ) : null}
      </View>
    </View>
  );
}
