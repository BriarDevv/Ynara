"use client";

import { chatErrorCopy, chatPausedCopy } from "@ynara/shared-schemas";
import { Button } from "@/components/ui/Button";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
import { cn } from "@/lib/cn";
import { useShowReasoningStore } from "@/stores/showReasoning";
import type { ChatUiMessage } from "../store";
import { Markdown } from "./Markdown";
import { MessageActions } from "./MessageActions";
import { ThinkingDisclosure } from "./ThinkingDisclosure";

/**
 * Una burbuja de la conversación.
 *
 * - Usuario: derecha, fondo ink suave, texto plano.
 * - Assistant: izquierda, hairline con el tint del modo, markdown sanitizado.
 * - Error: burbuja de sistema con copy humano (mapeado de `errorCode`) +
 *   botón reintentar (el handler lo pasa el padre).
 * - Canceled: el parcial que alcanzó a llegar + un pie sutil "Respuesta
 *   cancelada", para distinguirlo de una respuesta completa (el cancel sin
 *   ningún token descarta la burbuja en el store, así que acá siempre hay
 *   parcial).
 *
 * El cursor de streaming y el render token-a-token llegan en W3; acá el
 * status "streaming" se trata como texto parcial sin cursor.
 */
type Props = {
  message: ChatUiMessage;
  mode: ModeId;
  /** Reintentar el envío del mensaje del usuario que falló. */
  onRetry?: () => void;
};

export function MessageBubble({ message, mode, onRetry }: Props) {
  // Toggle display-only: SOLO decide si se renderiza el colapsable de
  // razonamiento (no controla el thinking del modelo). Se lee acá arriba, antes
  // de los early returns, para no romper el orden de hooks.
  const showReasoning = useShowReasoningStore((s) => s.enabled);

  if (message.status === "error") {
    return (
      <div role="alert" className="flex flex-col items-start gap-2">
        <div className="max-w-[85%] rounded-[var(--radius-md)] border border-[var(--color-error)] bg-[var(--color-error-soft)] px-4 py-3">
          <p className="text-body text-[var(--color-ink)]">{chatErrorCopy(message.errorCode)}</p>
        </div>
        {onRetry ? (
          <Button variant="ghost" onClick={onRetry} className="px-3 py-1.5 text-body-sm">
            Reintentar
          </Button>
        ) : null}
      </div>
    );
  }

  if (message.status === "degraded") {
    // IA no disponible (ADR-027): estado calmo/informativo, NO el rojo de error
    // (no es un fallo del turno del usuario). El anuncio a lectores de pantalla
    // lo hace la región viva PERSISTENTE de MessageList (un `role="status"`
    // recién montado acá no dispara el anuncio de forma confiable), por eso el
    // bubble es un div plano. El texto enlatado del backend ya se descartó en el
    // store; mostramos el copy honesto. El composer queda habilitado, así que el
    // usuario puede reintentar escribiendo de nuevo cuando la IA vuelva.
    return (
      <div className="flex flex-col items-start gap-2">
        <div className="max-w-[85%] rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] px-4 py-3">
          <p className="text-body-sm text-[var(--color-ink-soft)]">{chatPausedCopy()}</p>
        </div>
      </div>
    );
  }

  if (message.role === "user") {
    // Burbuja teñida por el modo (mockup): fondo del color del modo a baja
    // opacidad + borde sutil, esquina inferior-derecha más cerrada. El texto
    // queda en ink (legible sobre el tinte suave, en claro y en Noche).
    const tintVar = MODE_BY_ID[mode].tintVar;
    return (
      <div className="flex justify-end">
        <div
          className={cn(
            "max-w-[85%] whitespace-pre-wrap rounded-[var(--radius-xl)] rounded-br-[7px] border px-4 py-2.5 text-body text-[var(--color-ink)]",
            message.status === "sending" && "opacity-70",
          )}
          style={{
            backgroundColor: `color-mix(in srgb, ${tintVar} 14%, var(--color-bg))`,
            borderColor: `color-mix(in srgb, ${tintVar} 30%, transparent)`,
          }}
        >
          {message.text}
        </div>
      </div>
    );
  }

  // assistant (incluye "canceled": parcial + pie sutil)
  const canceled = message.status === "canceled";
  return (
    <div className="flex justify-start">
      <div className="flex max-w-[85%] gap-3">
        <span
          aria-hidden
          className="mt-1 w-0.5 shrink-0 self-stretch rounded-[var(--radius-pill)]"
          style={{ backgroundColor: MODE_BY_ID[mode].tintVar }}
        />
        <div className="text-body text-[var(--color-ink)]">
          {showReasoning && message.reasoning && message.reasoning.length > 0 ? (
            <ThinkingDisclosure
              reasoning={message.reasoning}
              // "Pensando…" mientras el stream sigue abierto y la respuesta aún
              // no empezó; al llegar el primer token de la respuesta, colapsa.
              streaming={message.status === "streaming" && message.text.length === 0}
            />
          ) : null}
          <Markdown>{message.text}</Markdown>
          {message.actions && message.actions.length > 0 ? (
            <MessageActions actions={message.actions} mode={mode} />
          ) : null}
          {canceled ? (
            <p className="mt-1.5 text-caption text-[var(--color-ink-soft)]">Respuesta cancelada</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
