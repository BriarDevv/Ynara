import type { Mode } from "@ynara/shared-schemas";
import { useRouter } from "expo-router";
import { Pressable, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { MODE_DESCRIPTORS, MODE_DOT_CLASS } from "@/components/ui/modes";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";
import { useChatStore } from "@/stores/chat";
import { useUserStore } from "@/stores/user";
import { SessionsList } from "./SessionsList";

/**
 * Entrada del chat (M4) post-onboarding: conversaciones recientes (retomar) +
 * "empezar una nueva" (los 5 modos, primero los elegidos en el onboarding). No
 * hay home mobile todavía (FRONTEND-CHAT-PLAN); esta pantalla cumple ese rol.
 * Elegir un modo crea una sesión (una sesión = un modo) y navega a la conversación.
 */
export function ChatHome() {
  const router = useRouter();
  const createSession = useChatStore((s) => s.createSession);
  const interestedModes = useUserStore((s) => s.interestedModes);

  const ordered = [...MODE_DESCRIPTORS].sort(
    (a, b) => Number(interestedModes.includes(b.id)) - Number(interestedModes.includes(a.id)),
  );

  const start = (mode: Mode) => {
    const id = createSession(mode);
    router.push({ pathname: "/chat/[sessionId]", params: { sessionId: id } });
  };

  return (
    <SafeAreaView className="flex-1 bg-bg-canvas" edges={["top", "bottom"]}>
      <ScrollView contentContainerClassName="gap-6 px-6 py-8">
        <View className="gap-2">
          <Text className="text-title font-display text-ink-deep">¿De qué hablamos?</Text>
          <Text className="text-body text-ink-soft">
            Retomá una conversación o empezá una nueva.
          </Text>
        </View>

        <SessionsList />

        <View className="gap-3">
          <Text className="text-caption text-ink-soft">EMPEZAR UNA NUEVA</Text>
          <View className="gap-3">
            {ordered.map((m) => (
              <Pressable
                key={m.id}
                accessibilityRole="button"
                onPress={() => start(m.id)}
                className="rounded-lg border border-border bg-bg p-4 active:bg-bg-soft"
              >
                <View className="flex-row items-center gap-3">
                  <View className={cn("h-3 w-3 rounded-pill", MODE_DOT_CLASS[m.id])} />
                  <View className="flex-1">
                    <Text className="text-body font-body-semibold text-ink">{m.label}</Text>
                    <Text className="text-body-sm text-ink-soft">{m.blurb}</Text>
                  </View>
                </View>
              </Pressable>
            ))}
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
