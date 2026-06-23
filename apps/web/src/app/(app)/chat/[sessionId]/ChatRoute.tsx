"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { ChatScreen } from "@/features/chat/components/ChatScreen";
import { useChatStore } from "@/features/chat/store";

/**
 * Dispatcher cliente de la pantalla de conversación. Guard de sesión:
 * si el `sessionId` de la URL no existe en el store → redirect a `/hoy`
 * (el toast "Conversación no encontrada" lo levanta la home con el query
 * param `?notfound=chat`; W5 lo consume, hoy queda inerte).
 *
 * El guard de onboarding ya no vive acá: lo centraliza el layout del route
 * group `(app)`. El de sesión sí va en cliente porque el store de sesiones
 * vive en localStorage (el server no sabe qué sesiones existen).
 */
export function ChatRoute({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  // Guard effect: reacciona al store de sesiones (zustand, vive en localStorage),
  // no a un evento de UI; no hay handler donde mover esta lógica de redirect.
  // react-doctor-disable-next-line react-doctor/no-event-handler
  const sessionExists = useChatStore((s) => Boolean(s.sessions[sessionId]));

  useEffect(() => {
    if (!sessionExists) {
      // Guard client-only: el store de sesiones vive en localStorage (zustand);
      // el server no sabe qué sesiones existen, un redirect SSR no aplica.
      // react-doctor-disable-next-line react-doctor/nextjs-no-client-side-redirect
      router.replace("/hoy?notfound=chat");
    }
  }, [sessionExists, router]);

  // El "checked" derivado de `sessionExists` reemplaza el antiguo estado +
  // effect (que adjustaba estado tras cambiar el prop, forzando un render
  // extra con UI stale). Si la sesión no existe → null mientras el effect
  // dispara el redirect (evita flashear la pantalla antes de irse).
  if (!sessionExists) return null;

  return <ChatScreen sessionId={sessionId} />;
}
