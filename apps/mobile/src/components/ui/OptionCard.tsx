import type { ReactNode } from "react";
import { Pressable, View } from "react-native";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";

type Props = {
  title: string;
  hint?: string;
  selected?: boolean;
  disabled?: boolean;
  onPress?: () => void;
  /** Slot a la izquierda (icono, ModeChip, etc.). */
  leading?: ReactNode;
  className?: string;
};

/**
 * Card seleccionable (RN). Espejo del `OptionCard` de la web: fondo blanco
 * que se distingue por un borde azul de marca cuando está seleccionado (en RN
 * usamos border en vez del ring inset de la web). Para listas tipo Mood/Modos.
 */
export function OptionCard({
  title,
  hint,
  selected = false,
  disabled = false,
  onPress,
  leading,
  className,
}: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected, disabled }}
      disabled={disabled}
      onPress={onPress}
      className={cn(
        "w-full rounded-md border-2 bg-bg p-4 active:opacity-90",
        selected ? "border-blue-flat" : "border-border",
        disabled && "opacity-50",
        className,
      )}
    >
      <View className="flex-row items-center gap-3">
        {leading ? <View className="shrink-0">{leading}</View> : null}
        <View className="flex-1 flex-col">
          <Text className="text-body font-medium text-ink-deep">{title}</Text>
          {hint ? <Text className="text-body-sm text-ink-soft">{hint}</Text> : null}
        </View>
      </View>
    </Pressable>
  );
}
