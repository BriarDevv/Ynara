import { Redirect } from "expo-router";
import { ChatHome } from "@/features/chat/ChatHome";
import { useUserStore } from "@/stores/user";

// Entrada de la app: sin onboarding completo → flujo de onboarding; ya
// onboardeado → home del chat (conversaciones recientes + empezar una nueva).
// No hay home mobile general todavía (FRONTEND-CHAT-PLAN M4).
export default function Index() {
  const onboardingCompleted = useUserStore((s) => s.onboardingCompleted);

  if (!onboardingCompleted) {
    return <Redirect href="/onboarding" />;
  }

  return <ChatHome />;
}
