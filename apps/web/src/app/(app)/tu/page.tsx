import type { Metadata } from "next";
import { TuView } from "@/features/profile/components/TuView";

export const metadata: Metadata = {
  title: "Tú",
};

/**
 * Tab **Tú** (build-plan Fase G): perfil, memoria, a11y y cuenta. La page
 * (server) aporta el título; la vista real es client (`TuView`, hooks + fondo
 * vivo). El guard del grupo `(app)` exige onboarding completo.
 */
export default function TuPage() {
  return <TuView />;
}
