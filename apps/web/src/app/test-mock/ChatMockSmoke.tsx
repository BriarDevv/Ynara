"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ChatResponse } from "@ynara/shared-schemas";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { MODES, type ModeId } from "@/components/ui/modes";
import type { ApiError } from "@/lib/api";
import { sendChatMessage } from "@/lib/chat";
import { qk } from "@/lib/queryKeys";

/**
 * Smoke de `POST /v1/chat` (W1): manda un mensaje en el modo elegido y muestra
 * el `ChatResponse` mockeado. Sirve para verificar a ojo que el handler MSW
 * responde por modo y que los modos Qwen traen `actions`.
 */
export function ChatMockSmoke() {
  const [mode, setMode] = useState<ModeId>("productividad");
  const queryClient = useQueryClient();
  const mutation = useMutation<ChatResponse, ApiError, ModeId>({
    mutationFn: (m) => sendChatMessage({ text: "Hola, esto es un smoke test", mode: m }),
    // Mandar un mensaje puede crear/actualizar la sesión: refrescar el listado.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.sessions.all() });
    },
  });

  return (
    <Card>
      <div className="flex flex-col gap-4">
        <p className="text-caption text-[var(--color-ink-soft)]">POST /v1/chat</p>
        <div className="flex flex-wrap gap-2">
          {MODES.map((m) => (
            <Button
              key={m.id}
              variant={m.id === mode ? "primary" : "secondary"}
              onClick={() => setMode(m.id)}
            >
              {m.label}
            </Button>
          ))}
        </div>
        <Button onClick={() => mutation.mutate(mode)} disabled={mutation.isPending}>
          {mutation.isPending ? "Enviando…" : `Enviar en modo ${mode}`}
        </Button>
        {mutation.error ? (
          <p className="text-body text-[var(--color-error)]">
            Error {mutation.error.status}: {mutation.error.message}
          </p>
        ) : null}
        {mutation.data ? (
          <pre className="text-body-sm overflow-x-auto rounded-[var(--radius-md)] bg-[var(--color-bg-soft)] p-4 text-[var(--color-ink)]">
            {JSON.stringify(mutation.data, null, 2)}
          </pre>
        ) : null}
      </div>
    </Card>
  );
}
