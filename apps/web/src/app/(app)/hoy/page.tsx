import { HoyView } from "@/features/today/components/HoyView";

/**
 * Tab **Hoy** — la home real de la app, dentro del app shell (build-plan
 * §3.1 / Fase A). Renderiza el dashboard Hoy (header + prioridades del día;
 * sugerencias y recap se suman en E3/E4). El título lo aporta el layout.
 *
 * El cierre del onboarding lo flipea `CelebrationOutro` al navegar (el guard del
 * grupo `(app)` exige `onboardingCompleted` antes de montar esta vista).
 */
export default function HoyPage() {
  return <HoyView />;
}
