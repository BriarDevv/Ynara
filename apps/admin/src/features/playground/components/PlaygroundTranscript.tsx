"use client";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { cn } from "@/lib/cn";
import { playgroundErrorCopy } from "../hooks/usePlayground";
import type { PlaygroundOutT } from "../schemas";

type Props = {
  /** Si el serving es real; `false` muestra el aviso en vez del transcript. */
  isReal: boolean;
  /** El mensaje del operador del último turno (null = sin turno todavía). */
  userMessage: string | null;
  /** La respuesta del turno (null mientras no llegó). */
  result: PlaygroundOutT | null;
  /** True mientras la mutation está en vuelo (cursor pulsante). */
  isPending: boolean;
  /** El error del turno (null si no hubo). */
  error: unknown;
  /** Reintenta el último envío. */
  onRetry: () => void;
  className?: string;
};

/**
 * Banda 2 del Playground (ADR-018 §3): el transcript del turno.
 *
 * `min-h` fijo para que el layout no salte entre estados. Orden de prioridad:
 *  1. `!isReal` → aviso de serving fake (no se puede generar).
 *  2. sin turno → empty state.
 *  3. burbuja del operador (derecha) + respuesta:
 *     - `isPending` → burbuja assistant con cursor pulsante `▍`.
 *     - `error`     → caja de error por status (copy neutro) + "Reintentar".
 *     - `result`    → burbuja assistant (texto plano `whitespace-pre-wrap`, v1
 *                     sin markdown) + footer de métricas `tabular-nums`.
 */
export function PlaygroundTranscript({
  isReal,
  userMessage,
  result,
  isPending,
  error,
  onRetry,
  className,
}: Props) {
  return (
    <Card className={cn("flex min-h-[18rem] flex-col gap-4", className)}>
      {!isReal ? (
        <EmptyStateCard
          title="Serving fake: no hay generación real."
          hint="Corré el backend con LLM_BACKEND=vllm para probar el modelo desde acá."
        />
      ) : !userMessage ? (
        <EmptyStateCard title="Mandá un mensaje para probar el modelo." />
      ) : (
        <div className="flex flex-col gap-4">
          <UserBubble text={userMessage} />
          {error ? (
            <ErrorBox error={error} onRetry={onRetry} />
          ) : isPending ? (
            <PendingBubble />
          ) : result ? (
            <AssistantBubble result={result} />
          ) : null}
        </div>
      )}
    </Card>
  );
}

/** Burbuja del operador, alineada a la derecha sobre `bg-soft`. */
function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[80%] whitespace-pre-wrap rounded-[var(--radius-md)] bg-[var(--color-bg-soft)] px-4 py-3 text-body text-[var(--color-ink)]">
        {text}
      </p>
    </div>
  );
}

/** Burbuja del assistant en vuelo: cursor pulsante mientras se genera. */
function PendingBubble() {
  return (
    <div className="flex justify-start">
      <p className="rounded-[var(--radius-md)] border border-[var(--color-border)] px-4 py-3 text-body text-[var(--color-ink)]">
        <span aria-hidden className="anim-pulse-soft inline-block">
          ▍
        </span>
        <span className="sr-only">Generando respuesta…</span>
      </p>
    </div>
  );
}

/** Burbuja del assistant con la respuesta + footer de métricas (tabular-nums). */
function AssistantBubble({ result }: { result: PlaygroundOutT }) {
  return (
    <div className="flex justify-start">
      <div className="flex max-w-[80%] flex-col gap-3 rounded-[var(--radius-md)] border border-[var(--color-border)] px-4 py-3">
        <p className="whitespace-pre-wrap text-body text-[var(--color-ink)]">{result.text}</p>
        <footer className="flex flex-wrap gap-x-4 gap-y-1 border-t border-[var(--color-border)] pt-2 text-caption text-[var(--color-ink-soft)]">
          <span className="text-[var(--color-ink)]">{result.model_name}</span>
          <span>{result.finish_reason}</span>
          <span className="tabular-nums">
            {result.prompt_tokens}+{result.completion_tokens} tok
          </span>
          <span className="tabular-nums">{Math.round(result.latency_ms)}ms</span>
          <span>thinking {result.thinking_used ? "on" : "off"}</span>
        </footer>
      </div>
    </div>
  );
}

/** Caja de error por status (copy neutro, regla #4) + botón reintentar. */
function ErrorBox({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const { title, hint } = playgroundErrorCopy(error);
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-2 rounded-[var(--radius-md)] border border-[var(--color-error)] bg-[var(--color-error-soft)] px-4 py-3"
    >
      <p className="text-body-sm text-[var(--color-ink)]">{title}</p>
      <p className="text-caption text-[var(--color-ink-soft)]">{hint}</p>
      <Button variant="ghost" onClick={onRetry} className="mt-1">
        Reintentar
      </Button>
    </div>
  );
}
