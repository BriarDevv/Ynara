import type { Mode } from "@ynara/shared-schemas";
import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { LivingField } from "@/components/ui/LivingField";
import { useChatStore } from "@/stores/chat";
import { useChatSessionStore } from "@/stores/chatSession";
import { useUserStore } from "@/stores/user";
import { ChatConversation } from "./ChatConversation";
import { ChatModeSheet } from "./components/ChatModeSheet";
import { ChatTopBar } from "./components/ChatTopBar";
import { RecentsSheet } from "./components/RecentsSheet";
import { mostRecentSessionOfMode, shouldResume } from "./session";

/**
 * Tab de Chat: entrás y ya estás en una conversación. Resuelve la sesión activa
 * con `useChatSessionStore` + timeout (reanuda si volviste hace <1 min; si no,
 * chat nuevo en el último modo). El modo (arriba-izq) lleva a la conversación de
 * ese modo; los recientes (arriba-der) saltan a cualquiera. Todo in-place.
 */
export function ChatTab() {
  const createSession = useChatStore((s) => s.createSession);
  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatSessionStore((s) => s.activeSessionId);
  const setActive = useChatSessionStore((s) => s.setActive);
  const markLeft = useChatSessionStore((s) => s.markLeft);
  const interestedModes = useUserStore((s) => s.interestedModes);

  const [modeOpen, setModeOpen] = useState(false);
  const [recentsOpen, setRecentsOpen] = useState(false);

  const defaultMode: Mode = interestedModes[0] ?? "productividad";

  // Al enfocar el tab: reanudar o abrir nueva (en el modo de la última). Al
  // salir: marcar lastActiveAt. Se lee el estado con getState() para no
  // re-ejecutar en cada cambio del store.
  useFocusEffect(
    useCallback(() => {
      const sess = useChatSessionStore.getState();
      const chat = useChatStore.getState();
      const activeOk =
        sess.activeSessionId !== null && chat.sessions[sess.activeSessionId] !== undefined;
      const resume = activeOk && shouldResume(sess.activeSessionId, sess.lastActiveAt, Date.now());
      if (!resume) {
        const lastMode = sess.activeSessionId
          ? chat.sessions[sess.activeSessionId]?.mode
          : undefined;
        setActive(createSession(lastMode ?? defaultMode));
      }
      return () => markLeft();
    }, [createSession, setActive, markLeft, defaultMode]),
  );

  const active = activeSessionId ? sessions[activeSessionId] : undefined;

  const switchToMode = (mode: Mode) => {
    setModeOpen(false);
    const existing = mostRecentSessionOfMode(sessions, mode);
    setActive(existing ? existing.id : createSession(mode));
  };

  const selectRecent = (id: string) => {
    setRecentsOpen(false);
    setActive(id);
  };

  const startNew = () => {
    setRecentsOpen(false);
    setActive(createSession(active?.mode ?? defaultMode));
  };

  return (
    <View className="flex-1 bg-bg-canvas">
      <LivingField variant="constellation" />
      <SafeAreaView className="flex-1" edges={["top", "bottom"]}>
        {active ? (
          <>
            <ChatTopBar
              mode={active.mode}
              onPressMode={() => setModeOpen(true)}
              onPressRecents={() => setRecentsOpen(true)}
            />
            <ChatConversation key={active.id} sessionId={active.id} />
            <ChatModeSheet
              open={modeOpen}
              current={active.mode}
              onClose={() => setModeOpen(false)}
              onSelect={switchToMode}
            />
            <RecentsSheet
              open={recentsOpen}
              onClose={() => setRecentsOpen(false)}
              onSelect={selectRecent}
              onNew={startNew}
            />
          </>
        ) : null}
      </SafeAreaView>
    </View>
  );
}
