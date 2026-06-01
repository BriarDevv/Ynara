import type { Metadata } from "next";
import { TabPlaceholder } from "@/components/TabPlaceholder";

export const metadata: Metadata = {
  title: "Buscar",
};

/**
 * Sub-vista **Búsqueda**. Stub hasta la Fase C (endpoint chico
 * `GET /v1/memory/search?q=`): search bar, skeleton de carga, "N RESULTADOS",
 * empty state.
 */
export default function BuscarPage() {
  return (
    <TabPlaceholder
      icon="buscar"
      title="Buscar"
      hint="Encontrá cualquier cosa que Ynara haya guardado por vos. Próximamente."
    />
  );
}
