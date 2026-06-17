import { forwardRef } from "react";
import { TextInput, type TextInputProps, View } from "react-native";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";

type Props = Omit<TextInputProps, "className"> & {
  label?: string;
  hint?: string;
  /** Mensaje de error inline. Si está presente, marca el campo como inválido. */
  error?: string;
  className?: string;
};

// ink-soft (rgba(36,44,63,0.70)) — el placeholder va por prop, no por className.
const PLACEHOLDER_COLOR = "rgba(243,240,234,0.40)";

/**
 * Campo de texto base (RN). Espejo del `TextField` de la web, portado a
 * TextInput con label/hint/error. El foco usa el ring nativo del SO.
 */
export const TextField = forwardRef<TextInput, Props>(function TextField(
  { label, hint, error, className, ...rest },
  ref,
) {
  const invalid = Boolean(error);

  return (
    <View className={cn("w-full flex-col gap-1.5", className)}>
      {label ? <Text className="text-caption text-ink-soft">{label}</Text> : null}
      <TextInput
        ref={ref}
        placeholderTextColor={PLACEHOLDER_COLOR}
        className={cn(
          "text-body w-full rounded-md border bg-bg px-4 py-3.5 text-ink",
          invalid ? "border-error" : "border-border",
        )}
        {...rest}
      />
      {error ? (
        <Text className="text-body-sm text-error">{error}</Text>
      ) : hint ? (
        <Text className="text-body-sm text-ink-soft">{hint}</Text>
      ) : null}
    </View>
  );
});
