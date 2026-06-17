import { Pressable, View } from "react-native";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";

type ChipOption<T extends string> = {
  value: T;
  label: string;
};

type Props<T extends string> = {
  label?: string;
  options: readonly ChipOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
};

/**
 * Grupo de pills single-select (RN). Espejo del `ChipGroup` de la web: track
 * crema con la pill seleccionada en blanco. Para opciones tipo tamaño de texto.
 */
export function ChipGroup<T extends string>({
  label,
  options,
  value,
  onChange,
  className,
}: Props<T>) {
  return (
    <View className={cn("gap-3", className)}>
      {label ? <Text className="text-caption text-ink-soft">{label}</Text> : null}
      <View className="flex-row self-start gap-2 rounded-pill bg-bg-soft p-1">
        {options.map((opt) => {
          const selected = opt.value === value;
          return (
            <Pressable
              key={opt.value}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              onPress={() => onChange(opt.value)}
              className={cn("rounded-pill px-4 py-2", selected && "bg-bg")}
            >
              <Text className={cn("text-button", selected ? "text-ink" : "text-ink-soft")}>
                {opt.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}
