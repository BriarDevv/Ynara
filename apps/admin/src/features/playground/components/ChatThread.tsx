"use client";

import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/Button";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { cn } from "@/lib/cn";
import type { ChatTurn } from "@/stores/playgroundSessions";
import { playgroundStatusCopy } from "../hooks/usePlayground";
import type { LiveTurn } from "../hooks/usePlaygroundStream";

type Props = {
  messages: readonly ChatTurn[];
  live: LiveTurn;
  /** Modo agente en vuelo (mutation sync, sin streaming): burbuja "pensando". */
  agentPending: boolean;
  isReal: boolean;
  onRetry: () => void;
  className?: string;
};

/**
 * El hilo de chat — la superficie protagonista del Playground rediseñado.
 *
 * Renderiza la conversación COMPLETA de la sesión activa (no el último turno):
 * burbujas user (derecha) + assistant (izquierda) con su texto, el thinking
 * colapsable (qwen) y el footer de métricas (`tabular-nums`). El turno en vuelo
 * se pinta token-por-token desde `live` (cursor pulsante, thinking en vivo,
 * tok/s). Autoscroll al fondo en cada delta. Sin turno → empty state.
 */
export function ChatThread({ messages, live, agentPending, isReal, onRetry, className }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Autoscroll: al fondo en cada mensaje nuevo o delta del stream.
  // biome-ignore lint/correctness/useExhaustiveDependencies: el scroll debe correr en cada delta (live.rawText) y cada turno (messages.length).
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, live.rawText, live.phase, agentPending]);

  const empty = messages.length === 0 && live.phase === "idle" && !agentPending;

  if (!isReal) {
    return (
      <div className={cn("flex flex-1 items-center justify-center", className)}>
        <EmptyStateCard
          title="Serving fake: no hay generación real."
          hint="Corré el backend con LLM_BACKEND=vllm para chatear con el modelo."
        />
      </div>
    );
  }

  return (
    <div className={cn("flex flex-1 flex-col gap-5 overflow-y-auto scrollbar-none", className)}>
      {empty ? (
        <div className="flex flex-1 items-center justify-center">
          <EmptyStateCard
            title="Empezá una conversación con el modelo."
            hint="Escribí abajo. La respuesta se va a ver mientras se genera, token por token."
          />
        </div>
      ) : (
        <>
          {messages.map((turn) =>
            turn.role === "user" ? (
              <UserBubble key={turn.id} text={turn.content} />
            ) : (
              <AssistantTurn key={turn.id} turn={turn} onRetry={onRetry} />
            ),
          )}
          {live.phase === "streaming" ? <LiveBubble live={live} /> : null}
          {agentPending ? <PendingBubble label="Corriendo el tool-loop…" /> : null}
        </>
      )}
      <div ref={bottomRef} aria-hidden />
    </div>
  );
}

/** Burbuja del operador, alineada a la derecha. */
function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[82%] whitespace-pre-wrap rounded-[var(--radius-lg)] rounded-tr-[var(--radius-sm)] bg-[var(--color-bg-soft)] px-4 py-3 text-body text-[var(--color-ink)]">
        {text}
      </p>
    </div>
  );
}

/** Turno assistant persistido: ok (texto + thinking + métricas) o error (retry). */
function AssistantTurn({ turn, onRetry }: { turn: ChatTurn; onRetry: () => void }) {
  if (turn.status === "error") {
    return <ErrorBubble status={turn.errorStatus ?? null} onRetry={onRetry} />;
  }
  return (
    <div className="flex justify-start">
      <div className="flex max-w-[82%] flex-col gap-3 rounded-[var(--radius-lg)] rounded-tl-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg)] px-4 py-3">
        {turn.content ? (
          <p className="whitespace-pre-wrap text-body text-[var(--color-ink)]">{turn.content}</p>
        ) : (
          <p className="text-body-sm text-[var(--color-ink-soft)]">
            (respuesta vacía — probá con thinking apagado o más tokens)
          </p>
        )}
        {turn.thinking ? <ThinkingDisclosure thinking={turn.thinking} /> : null}
        <TurnFooter turn={turn} />
      </div>
    </div>
  );
}

/** Burbuja en vivo: texto streameado + cursor + thinking en vivo + tok/s. */
function LiveBubble({ live }: { live: LiveTurn }) {
  return (
    <div className="flex justify-start">
      <div className="flex max-w-[82%] flex-col gap-3 rounded-[var(--radius-lg)] rounded-tl-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg)] px-4 py-3">
        {live.thinking ? <ThinkingDisclosure thinking={live.thinking} live /> : null}
        <p
          aria-live="polite"
          aria-atomic="false"
          className="whitespace-pre-wrap text-body text-[var(--color-ink)]"
        >
          {live.text}
          <span
            aria-hidden
            className="anim-pulse-soft ml-0.5 inline-block text-[var(--color-blue-flat)]"
          >
            ▍
          </span>
          <span className="sr-only">Generando respuesta…</span>
        </p>
        <footer className="flex flex-wrap gap-x-4 gap-y-1 border-t border-[var(--color-border)] pt-2 text-caption text-[var(--color-ink-soft)]">
          <span className="tabular-nums">{live.tokensPerSecond.toFixed(1)} tok/s</span>
          <span className="tabular-nums">{live.completionTokens} tok</span>
        </footer>
      </div>
    </div>
  );
}

/** Burbuja "pensando" para el modo agente (sync, sin streaming). */
function PendingBubble({ label }: { label: string }) {
  return (
    <div className="flex justify-start">
      <p className="rounded-[var(--radius-lg)] rounded-tl-[var(--radius-sm)] border border-[var(--color-border)] px-4 py-3 text-body text-[var(--color-ink-soft)]">
        <span
          aria-hidden
          className="anim-pulse-soft mr-1 inline-block text-[var(--color-blue-flat)]"
        >
          ▍
        </span>
        {label}
      </p>
    </div>
  );
}

/** Footer de métricas del turno (tabular-nums; sin métricas en modo agente). */
function TurnFooter({ turn }: { turn: ChatTurn }) {
  if (turn.agent) {
    return (
      <footer className="border-t border-[var(--color-border)] pt-2 text-caption text-[var(--color-ink-soft)]">
        modo agente · tools en el inspector
      </footer>
    );
  }
  return (
    <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--color-border)] pt-2 text-caption text-[var(--color-ink-soft)]">
      {turn.model ? <span className="text-[var(--color-ink)]">{turn.model}</span> : null}
      {turn.finishReason ? <span>{turn.finishReason}</span> : null}
      {turn.completionTokens != null ? (
        <span className="tabular-nums">{turn.completionTokens} tok</span>
      ) : null}
      {turn.tokensPerSecond != null ? (
        <span className="tabular-nums">{turn.tokensPerSecond.toFixed(1)} tok/s</span>
      ) : null}
      {turn.latencyMs != null ? (
        <span className="tabular-nums">{Math.round(turn.latencyMs)}ms</span>
      ) : null}
      <span>thinking {turn.thinkingUsed ? "on" : "off"}</span>
    </footer>
  );
}

/**
 * Bloque de thinking colapsable (`<details>` nativo). En vivo arranca ABIERTO
 * (`open`) para mostrar el razonamiento mientras streamea; persistido arranca
 * cerrado. Texto `font-mono` teñido violeta, igual que el inspector.
 */
function ThinkingDisclosure({ thinking, live = false }: { thinking: string; live?: boolean }) {
  return (
    <details className="group flex flex-col gap-2" open={live}>
      <summary className="flex cursor-pointer list-none items-center gap-2 text-body-sm text-[var(--color-violeta)]">
        <span
          aria-hidden
          className="inline-block transition-transform duration-[var(--duration-fast)] group-open:rotate-90"
        >
          ›
        </span>
        {live ? "Pensando…" : "Razonamiento del modelo"}
      </summary>
      <pre className="mt-1 max-h-64 overflow-y-auto whitespace-pre-wrap rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] px-3 py-2 font-mono text-caption text-[var(--color-violeta)] scrollbar-none">
        {thinking}
      </pre>
    </details>
  );
}

/** Burbuja de error por status (copy neutro, regla #4) + reintentar. */
function ErrorBubble({ status, onRetry }: { status: number | null; onRetry: () => void }) {
  const { title, hint } = playgroundStatusCopy(status);
  return (
    <div className="flex justify-start">
      <div
        role="alert"
        className="flex max-w-[82%] flex-col items-start gap-2 rounded-[var(--radius-lg)] rounded-tl-[var(--radius-sm)] border border-[var(--color-error)] bg-[var(--color-error-soft)] px-4 py-3"
      >
        <p className="text-body-sm text-[var(--color-ink)]">{title}</p>
        <p className="text-caption text-[var(--color-ink-soft)]">{hint}</p>
        <Button variant="ghost" onClick={onRetry} className="mt-1">
          Reintentar
        </Button>
      </div>
    </div>
  );
}
