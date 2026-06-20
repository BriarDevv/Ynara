import { useMemo, useState } from "react";
import { Pressable, ScrollView, useWindowDimensions, View } from "react-native";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import { ModeChip } from "@/components/ui/ModeChip";
import { Text } from "@/components/ui/Text";
import { TextField } from "@/components/ui/TextField";
import { cn } from "@/lib/cn";
import { relativeTime } from "@/lib/relativeTime";
import { useChatStore } from "@/stores/chat";
import { buildRecents, type TimeBucket } from "../recents";

type Props = {
  open: boolean;
  onClose: () => void;
  onSelect: (sessionId: string) => void;
  onNew: () => void;
};

const TIME_OPTIONS: readonly { value: TimeBucket; label: string }[] = [
  { value: "todos", label: "Todos" },
  { value: "hoy", label: "Hoy" },
  { value: "ayer", label: "Ayer" },
  { value: "semana", label: "Semana" },
  { value: "mes", label: "Mes" },
];

/**
 * Panel de chats recientes: header + búsqueda + filtro temporal fijos arriba,
 * y solo la lista scrollea. El nombre de cada chat es el auto-nombre derivado
 * del primer mensaje (ver `buildRecents`). "+ Nueva" abre una conversación vacía.
 */
export function RecentsSheet({ open, onClose, onSelect, onNew }: Props) {
  const sessions = useChatStore((s) => s.sessions);
  const messages = useChatStore((s) => s.messages);
  const [query, setQuery] = useState("");
  const [bucket, setBucket] = useState<TimeBucket>("todos");
  const { height } = useWindowDimensions();

  const total = Object.keys(sessions).length;
  const items = useMemo(
    () => buildRecents(sessions, messages, { query, bucket, now: Date.now() }),
    [sessions, messages, query, bucket],
  );

  return (
    <BottomSheet open={open} onClose={onClose}>
      {/* Tope de altura explícito (en px, sin depender de NativeWind para el
          límite crítico): el sheet no pasa del 80% de la pantalla, así el header
          y los filtros quedan fijos arriba y solo la lista —con flexShrink—
          scrollea adentro en vez de empujar todo fuera de la vista. */}
      <View style={{ maxHeight: Math.round(height * 0.8) }} className="gap-4 px-6 pb-6 pt-5">
        <View className="flex-row items-center justify-between">
          <Text className="text-title font-display text-ink-deep">Chats recientes</Text>
          <Button variant="subtle" onPress={onNew}>
            + Nueva
          </Button>
        </View>

        {total === 0 ? (
          <Text className="text-body-sm text-ink-soft">Todavía no hay conversaciones.</Text>
        ) : (
          <>
            <TextField
              value={query}
              onChangeText={setQuery}
              placeholder="Buscar por nombre"
              autoCapitalize="none"
              autoCorrect={false}
              returnKeyType="search"
              accessibilityLabel="Buscar chats por nombre"
            />
            {/* Filtro temporal: chips que envuelven (wrap, sin scroll) para que
                nunca se corten ni se salgan, entren los 5 en cualquier ancho. */}
            <View className="flex-row flex-wrap gap-2">
              {TIME_OPTIONS.map((opt) => {
                const selected = opt.value === bucket;
                return (
                  <Pressable
                    key={opt.value}
                    accessibilityRole="radio"
                    accessibilityState={{ selected }}
                    onPress={() => setBucket(opt.value)}
                    className={cn(
                      "rounded-pill border px-4 py-2",
                      selected ? "border-blue-flat bg-blue-flat" : "border-chip-border bg-chip",
                    )}
                  >
                    <Text
                      className={cn(
                        "text-button",
                        selected ? "font-body-semibold text-on-dark" : "text-ink-soft",
                      )}
                    >
                      {opt.label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>

            {items.length === 0 ? (
              <Text className="text-body-sm text-ink-soft">No hay chats que coincidan.</Text>
            ) : (
              <ScrollView
                style={{ flexShrink: 1 }}
                contentContainerClassName="gap-2"
                keyboardShouldPersistTaps="handled"
              >
                {items.map((item) => (
                  <Pressable
                    key={item.id}
                    accessibilityRole="button"
                    accessibilityLabel={`Abrir chat: ${item.name}`}
                    onPress={() => onSelect(item.id)}
                    className="gap-1.5 rounded-lg border border-border bg-bg p-4 active:bg-bg-soft"
                  >
                    <Text numberOfLines={1} className="text-body font-body-semibold text-ink">
                      {item.name}
                    </Text>
                    <View className="flex-row items-center justify-between">
                      <ModeChip mode={item.mode} />
                      <Text className="text-caption text-ink-muted">
                        {relativeTime(item.updatedAt)}
                      </Text>
                    </View>
                  </Pressable>
                ))}
              </ScrollView>
            )}
          </>
        )}
      </View>
    </BottomSheet>
  );
}
