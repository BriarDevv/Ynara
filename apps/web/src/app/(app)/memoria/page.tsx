import type { Metadata } from "next";
import { TabPlaceholder } from "@/components/TabPlaceholder";

export const metadata: Metadata = {
  title: "Memoria",
};

/**
 * Sub-vista **Memoria** (timeline). Stub hasta la Fase C, donde se conecta
 * al backend REAL (`GET /v1/memory`): lista cronológica + filtros por capa.
 */
export default function MemoriaPage() {
  return (
    <TabPlaceholder
      icon="memoria"
      title="Memoria"
      hint="Tu línea de tiempo de recuerdos, capa por capa. Próximamente."
    />
  );
}
