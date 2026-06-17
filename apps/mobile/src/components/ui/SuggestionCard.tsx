import type { Mode } from "@ynara/shared-schemas";
import { View } from "react-native";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";
import { MODE_DOT_CLASS } from "./modes";

type Props = {
  /** Modo que tinta la barra de acento; `null` = sugerencia transversal (neutro). */
  mode: Mode | null;
  title: string;
  subtitle?: string;
  className?: string;
};

/**
 * Sugerencia tintada por modo (display-only), espejo del `SuggestionCard` de web
 * (variante de la lista "Ynara sugiere" de Hoy): barra de acento del modo a la
 * izquierda + título + subtítulo (el "porqué"). Sin caja; el separador entre
 * ítems lo pone la lista (RN no soporta `divide-y`).
 */
export function SuggestionCard({ mode, title, subtitle, className }: Props) {
  return (
    <View className={cn("flex-row items-stretch gap-3 py-3.5", className)}>
      <View
        className={cn(
          "w-1 shrink-0 rounded-pill",
          mode ? MODE_DOT_CLASS[mode] : "bg-border-strong",
        )}
      />
      <View className="flex-1 gap-1">
        <Text className="text-body font-medium text-ink-deep">{title}</Text>
        {subtitle ? <Text className="text-body-sm text-ink-soft">{subtitle}</Text> : null}
      </View>
    </View>
  );
}
