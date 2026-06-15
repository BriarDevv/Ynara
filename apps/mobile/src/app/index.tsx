import { Redirect } from "expo-router";
import { ModePicker } from "@/features/chat/ModePicker";
import { useUserStore } from "@/stores/user";

// Entrada de la app: sin onboarding completo → flujo de onboarding; ya
// onboardeado → selector de modo del chat (no hay home mobile todavía;
// FRONTEND-CHAT-PLAN.md M4 la deja como follow-up).
export default function Index() {
  const onboardingCompleted = useUserStore((s) => s.onboardingCompleted);

  if (!onboardingCompleted) {
    return <Redirect href="/onboarding" />;
  }

  return <ModePicker />;
}
