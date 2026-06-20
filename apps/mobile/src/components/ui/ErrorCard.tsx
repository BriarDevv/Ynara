import { Pressable, View } from "react-native";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";

type Props = {
  /** Título del error (qué no se pudo hacer). */
  title: string;
  /** Detalle opcional (por qué / qué hacer). */
  hint?: string;
  onRetry: () => void;
  /** Deshabilita el botón mientras reintenta. */
  retrying?: boolean;
};

/**
 * Card de error con reintento — el estado `isError` de las secciones que hacen
 * fetch con retry (Hoy, Agenda, Memoria). Centraliza el bloque que estaba
 * repetido. (Buscar muestra un error sin retry, no usa este componente.)
 */
export function ErrorCard({ title, hint, onRetry, retrying }: Props) {
  return (
    <View className="gap-2 rounded-lg border border-border bg-bg p-4">
      <Text className="text-body text-ink">{title}</Text>
      {hint ? <Text className="text-body-sm text-ink-soft">{hint}</Text> : null}
      <Pressable accessibilityRole="button" onPress={onRetry} disabled={retrying} hitSlop={8}>
        <Text className={cn("text-button text-ink underline", retrying && "opacity-50")}>
          Reintentar
        </Text>
      </Pressable>
    </View>
  );
}
