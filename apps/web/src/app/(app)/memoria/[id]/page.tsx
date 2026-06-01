import type { Metadata } from "next";
import { TabPlaceholder } from "@/components/TabPlaceholder";

export const metadata: Metadata = {
  title: "Recuerdo",
};

/**
 * Sub-vista **Detalle de memoria**. Stub hasta la Fase C
 * (`GET /v1/memory/{layer}/{ref}`): quote grande, contexto, relacionados,
 * acciones (editar `PATCH`, borrar `DELETE`).
 */
export default function MemoriaDetallePage() {
  return (
    <TabPlaceholder
      icon="memoria"
      title="Recuerdo"
      hint="El detalle de un recuerdo, con su contexto y lo que se le conecta. En camino."
    />
  );
}
