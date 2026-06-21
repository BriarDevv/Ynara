"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import type { ModeId } from "@/components/ui/modes";
import { useChatStore } from "./store";

/**
 * Arranca una conversación nueva desde cualquier lado (Hoy, avisos): crea la
 * sesión en el modo dado y navega a `/chat/[id]`. Si se pasa `prefill`, lo manda
 * por `?q=` para que el composer arranque pre-cargado (sin auto-enviar; el
 * usuario revisa y manda). Convierte Hoy de tablero pasivo en launcher hacia la
 * conversación, que es donde vive el valor.
 */
export function useStartChat() {
  const router = useRouter();
  const createSession = useChatStore((s) => s.createSession);

  return useCallback(
    (mode: ModeId, prefill?: string) => {
      const id = createSession(mode);
      const trimmed = prefill?.trim();
      const url = trimmed ? `/chat/${id}?q=${encodeURIComponent(trimmed)}` : `/chat/${id}`;
      router.push(url);
    },
    [createSession, router],
  );
}
