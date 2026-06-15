import type { Mode } from "@ynara/shared-schemas";
import { useRouter } from "expo-router";
import { Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { MODE_DESCRIPTORS, MODE_DOT_CLASS } from "@/components/ui/modes";
import { cn } from "@/lib/cn";
import { useChatStore } from "@/stores/chat";
import { useUserStore } from "@/stores/user";

/**
 * Selector de modo: entrada post-onboarding (no hay home mobile todavía). Lista
 * los 5 modos — primero los que el usuario marcó en el onboarding — y al elegir
 * crea una sesión en ese modo y navega a la conversación. Una sesión = un modo
 * (plan §4.4): volver acá y elegir otro modo arranca una sesión nueva.
 */
export function ModePicker() {
  const router = useRouter();
  const createSession = useChatStore((s) => s.createSession);
  const interestedModes = useUserStore((s) => s.interestedModes);

  // Ordenar dejando primero los modos elegidos en el onboarding (estable).
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
          <Text className="text-title font-semibold text-ink-deep">¿De qué hablamos?</Text>
          <Text className="text-body text-ink-soft">
            Elegí un modo para arrancar una conversación.
          </Text>
        </View>
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
                  <Text className="text-body font-semibold text-ink">{m.label}</Text>
                  <Text className="text-body-sm text-ink-soft">{m.blurb}</Text>
                </View>
              </View>
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
