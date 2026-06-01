import type { Metadata } from "next";
import { ChatRoute } from "./ChatRoute";

export const metadata: Metadata = {
  title: "Conversación",
};

// El estado de sesión vive en el cliente (localStorage); la página solo
// extrae el param y delega en el dispatcher cliente, que aplica el guard de
// sesión. Vive dentro del route group `(app)`: hereda el shell (tab bar /
// sidebar) y el guard de onboarding del layout del grupo.
export const dynamic = "force-dynamic";

export default async function ChatSessionPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <ChatRoute sessionId={sessionId} />;
}
