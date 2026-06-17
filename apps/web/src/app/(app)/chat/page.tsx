import type { Metadata } from "next";
import { ChatHome } from "@/features/chat/components/ChatHome";

export const metadata: Metadata = {
  title: "Chat",
};

/**
 * Landing de la tab **Chat** dentro del shell (build-plan Fase D / chat plan
 * W5): conversaciones recientes + arranque de una nueva. La conversación en sí
 * vive en `/chat/[sessionId]`. La page queda como server component (exporta
 * `metadata`) y delega en el client `ChatHome`.
 */
export default function ChatTabPage() {
  return <ChatHome />;
}
