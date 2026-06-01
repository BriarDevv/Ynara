import type { Metadata } from "next";
import { TabPlaceholder } from "@/components/TabPlaceholder";

export const metadata: Metadata = {
  title: "Tú",
};

/**
 * Tab **Tú** (perfil/ajustes). Stub hasta la Fase G, donde se deriva del
 * design system (no hay wireframe): perfil + memoria/búsqueda + a11y +
 * retención/export/wipe + logout.
 */
export default function TuPage() {
  return (
    <TabPlaceholder
      icon="adaptacion"
      title="Tú"
      hint="Tu perfil, tu memoria y cómo Ynara se adapta a vos. En camino."
    />
  );
}
