import { CHAT_TEXT_MAX_LENGTH } from "@ynara/shared-schemas";
import { useState } from "react";
import { Pressable, TextInput, View } from "react-native";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";

type Props = {
  onSend: (text: string) => void;
  /** Mientras streamea la respuesta: input deshabilitado, botón pasa a "Detener". */
  busy: boolean;
  /** Cancela el stream en curso (botón "Detener"). */
  onCancel?: () => void;
};

const PLACEHOLDER_COLOR = "rgba(36,44,63,0.45)";
const COUNTER_THRESHOLD = CHAT_TEXT_MAX_LENGTH - 300;

/**
 * Composer del chat (RN): `TextInput` multiline + botón enviar. En touch el
 * envío es por botón explícito (no Enter). Bloquea vacío, pasado de largo
 * (límite ~4000, mirror del backend) y mientras `busy`; ahí el botón cancela.
 */
export function ChatComposer({ onSend, busy, onCancel }: Props) {
  const [text, setText] = useState("");
  const trimmed = text.trim();
  const tooLong = text.length > CHAT_TEXT_MAX_LENGTH;
  const canSend = trimmed.length > 0 && !tooLong && !busy;

  const handleSend = () => {
    if (!canSend) return;
    onSend(trimmed);
    setText("");
  };

  return (
    <View className="gap-1">
      <View className="flex-row items-end gap-2 rounded-md border border-border bg-bg p-2">
        <TextInput
          value={text}
          onChangeText={setText}
          editable={!busy}
          multiline
          placeholder="Escribí algo…"
          placeholderTextColor={PLACEHOLDER_COLOR}
          className="text-body max-h-32 flex-1 px-2 py-1.5 text-ink"
        />
        {busy ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Detener"
            onPress={onCancel}
            className="h-9 items-center justify-center rounded-pill border border-border-strong px-4"
          >
            <Text className="text-button text-ink">Detener</Text>
          </Pressable>
        ) : (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Enviar"
            onPress={handleSend}
            disabled={!canSend}
            className={cn(
              "h-9 w-9 items-center justify-center rounded-pill bg-blue-flat",
              !canSend && "opacity-40",
            )}
          >
            <Text className="text-button font-semibold text-on-dark">↑</Text>
          </Pressable>
        )}
      </View>
      {text.length >= COUNTER_THRESHOLD ? (
        <Text
          className={cn("px-2 text-right text-caption", tooLong ? "text-error" : "text-ink-soft")}
        >
          {text.length} / {CHAT_TEXT_MAX_LENGTH}
        </Text>
      ) : null}
    </View>
  );
}
