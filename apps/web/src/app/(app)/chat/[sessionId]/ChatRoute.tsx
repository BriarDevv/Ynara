"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
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
  const sessionExists = useChatStore((s) => Boolean(s.sessions[sessionId]));
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!sessionExists) {
      router.replace("/hoy?notfound=chat");
      return;
    }
    setChecked(true);
  }, [sessionExists, router]);

  // No renderizar la pantalla hasta validar (evita flash antes del redirect).
  if (!checked) return null;

  return <ChatScreen sessionId={sessionId} />;
}
