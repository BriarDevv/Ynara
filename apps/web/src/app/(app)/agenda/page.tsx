import type { Metadata } from "next";
import { TabPlaceholder } from "@/components/TabPlaceholder";

export const metadata: Metadata = {
  title: "Agenda",
};

/** Tab **Agenda**. Stub hasta la Fase F (día/semana con mock de eventos). */
export default function AgendaPage() {
  return (
    <TabPlaceholder
      icon="recordatorio"
      title="Agenda"
      hint="Tu día y tu semana, bloque por bloque. Próximamente."
    />
  );
}
