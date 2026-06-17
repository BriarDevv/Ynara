import { forwardRef } from "react";
import { TextInput, type TextInputProps, View } from "react-native";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";

type Props = Omit<TextInputProps, "className"> & {
  label?: string;
  hint?: string;
  error?: string;
  className?: string;
};

const PLACEHOLDER_COLOR = "rgba(36,44,63,0.45)";

/**
 * Sibling de TextField para texto multilínea (RN). Espejo del `Textarea` web:
 * mismos tokens de padding/border/hint para que un form que mezcle ambos se
 * lea coherente.
 */
export const Textarea = forwardRef<TextInput, Props>(function Textarea(
  { label, hint, error, className, ...rest },
  ref,
) {
  const invalid = Boolean(error);

  return (
    <View className={cn("w-full flex-col gap-1.5", className)}>
      {label ? <Text className="text-caption text-ink-soft">{label}</Text> : null}
      <TextInput
        ref={ref}
        multiline
        textAlignVertical="top"
        placeholderTextColor={PLACEHOLDER_COLOR}
        className={cn(
          "text-body min-h-24 w-full rounded-md border bg-bg px-4 py-3.5 text-ink",
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
