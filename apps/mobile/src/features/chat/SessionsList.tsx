import { useRouter } from "expo-router";
import { Pressable, Text, View } from "react-native";
import { ModeChip } from "@/components/ui/ModeChip";
import { relativeTime } from "@/lib/relativeTime";
import { useChatStore } from "@/stores/chat";

/**
 * Conversaciones recientes (M4): lista las sesiones del chat store ordenadas por
 * `updatedAt`, con ModeChip + preview del último mensaje + tiempo relativo. Tap →
 * retoma `/chat/[sessionId]`. Devuelve null si no hay sesiones (la pantalla de
 * entrada muestra solo "empezar una nueva").
 */
export function SessionsList() {
  const router = useRouter();
  const sessions = useChatStore((s) => s.sessions);
  const messages = useChatStore((s) => s.messages);

  const ordered = Object.values(sessions).sort((a, b) => b.updatedAt - a.updatedAt);
  if (ordered.length === 0) return null;

  const preview = (sessionId: string): string => {
    const list = messages[sessionId] ?? [];
    for (let i = list.length - 1; i >= 0; i--) {
      const text = list[i]?.text.trim();
      if (text) return text;
    }
    return "Conversación vacía";
  };

  return (
    <View className="gap-3">
      <Text className="text-caption text-ink-soft">CONVERSACIONES RECIENTES</Text>
      <View className="gap-2">
        {ordered.map((session) => (
          <Pressable
            key={session.id}
            accessibilityRole="button"
            onPress={() =>
              router.push({ pathname: "/chat/[sessionId]", params: { sessionId: session.id } })
            }
            className="gap-1.5 rounded-lg border border-border bg-bg p-4 active:bg-bg-soft"
          >
            <View className="flex-row items-center justify-between">
              <ModeChip mode={session.mode} />
              <Text className="text-caption text-ink-muted">{relativeTime(session.updatedAt)}</Text>
            </View>
            <Text numberOfLines={1} className="text-body-sm text-ink-soft">
              {preview(session.id)}
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}
