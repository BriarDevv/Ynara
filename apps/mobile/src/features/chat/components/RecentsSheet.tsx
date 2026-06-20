import { Pressable, ScrollView, View } from "react-native";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import { ModeChip } from "@/components/ui/ModeChip";
import { Text } from "@/components/ui/Text";
import { relativeTime } from "@/lib/relativeTime";
import { useChatStore } from "@/stores/chat";

type Props = {
  open: boolean;
  onClose: () => void;
  onSelect: (sessionId: string) => void;
  onNew: () => void;
};

/** Panel de conversaciones recientes (ordenadas por updatedAt) + "+ Nueva". */
export function RecentsSheet({ open, onClose, onSelect, onNew }: Props) {
  const sessions = useChatStore((s) => s.sessions);
  const messages = useChatStore((s) => s.messages);
  const ordered = Object.values(sessions).sort((a, b) => b.updatedAt - a.updatedAt);

  const preview = (sessionId: string): string => {
    const list = messages[sessionId] ?? [];
    for (let i = list.length - 1; i >= 0; i--) {
      const text = list[i]?.text.trim();
      if (text) return text;
    }
    return "Conversación vacía";
  };

  return (
    <BottomSheet open={open} onClose={onClose}>
      <View className="gap-4 px-6 pb-6 pt-5">
        <View className="flex-row items-center justify-between">
          <Text className="text-title font-display text-ink-deep">Conversaciones</Text>
          <Button variant="subtle" onPress={onNew}>
            + Nueva
          </Button>
        </View>

        {ordered.length === 0 ? (
          <Text className="text-body-sm text-ink-soft">Todavía no hay conversaciones.</Text>
        ) : (
          <ScrollView className="max-h-96" contentContainerClassName="gap-2">
            {ordered.map((session) => (
              <Pressable
                key={session.id}
                accessibilityRole="button"
                onPress={() => onSelect(session.id)}
                className="gap-1.5 rounded-lg border border-border bg-bg p-4 active:bg-bg-soft"
              >
                <View className="flex-row items-center justify-between">
                  <ModeChip mode={session.mode} />
                  <Text className="text-caption text-ink-muted">
                    {relativeTime(session.updatedAt)}
                  </Text>
                </View>
                <Text numberOfLines={1} className="text-body-sm text-ink-soft">
                  {preview(session.id)}
                </Text>
              </Pressable>
            ))}
          </ScrollView>
        )}
      </View>
    </BottomSheet>
  );
}
