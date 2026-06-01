import type { Metadata } from "next";
import { TabPlaceholder } from "@/components/TabPlaceholder";

export const metadata: Metadata = {
  title: "Chat",
};

/**
 * Landing de la tab **Chat** dentro del shell. Stub hasta la Fase D (chat
 * plan W3+), donde se vuelve la lista de conversaciones + arranque de sesión.
 * La conversación en sí ya vive en `/chat/[sessionId]`.
 */
export default function ChatTabPage() {
  return (
    <TabPlaceholder
      icon="dialogo"
      title="Tus conversaciones"
      hint="Acá vas a arrancar y retomar tus charlas con Ynara. Lo estamos construyendo."
    />
  );
}
