import type { Metadata } from "next";
import { AgendaView } from "@/features/agenda/components/AgendaView";

export const metadata: Metadata = {
  title: "Agenda",
};

/**
 * Tab **Agenda** (build-plan Fase F): el día/semana de bloques horarios. La page
 * (server) aporta el título; la vista real es client (`AgendaView`, hooks +
 * fondo vivo). El guard del grupo `(app)` exige onboarding completo.
 */
export default function AgendaPage() {
  return <AgendaView />;
}
