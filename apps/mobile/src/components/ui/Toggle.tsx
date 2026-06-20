import { Pressable, View } from "react-native";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";

type Props = {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
};

/**
 * Switch (RN). Espejo del `Toggle` de la web: track azul de marca cuando está
 * on, thumb blanco. Usa accessibilityRole "switch".
 */
export function Toggle({ label, hint, checked, onChange, disabled = false, className }: Props) {
  return (
    <View className={cn("flex-row items-start gap-4", className)}>
      <View className="flex-1 flex-col gap-1">
        <Text className="text-body text-ink">{label}</Text>
        {hint ? <Text className="text-body-sm text-ink-soft">{hint}</Text> : null}
      </View>
      <Pressable
        accessibilityRole="switch"
        accessibilityState={{ checked, disabled }}
        disabled={disabled}
        onPress={() => onChange(!checked)}
        // Área táctil ≥44px: el track visible mide 28px de alto.
        hitSlop={8}
        className={cn(
          "h-7 w-12 shrink-0 justify-center rounded-pill px-1",
          checked ? "bg-blue-flat" : "bg-border-strong",
          disabled && "opacity-50",
        )}
      >
        <View
          className={cn("h-5 w-5 rounded-pill bg-on-dark", checked ? "self-end" : "self-start")}
        />
      </Pressable>
    </View>
  );
}
