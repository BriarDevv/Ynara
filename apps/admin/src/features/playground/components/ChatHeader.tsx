"use client";

import { cn } from "@/lib/cn";
import type { ServingModelOutT } from "../schemas";

type Props = {
  sessionTitle: string | null;
  activeModel: ServingModelOutT | undefined;
  isStreaming: boolean;
  liveTokensPerSecond: number;
  liveTokens: number;
  thinkingOn: boolean;
  agentMode: boolean;
  onClear: () => void;
  canClear: boolean;
};

/**
 * Cabecera del chat (tope de la columna protagonista). Mantiene SIEMPRE visible
 * qué modelo está activo (nombre mono + dot de salud + role) y, mientras
 * streamea, el medidor de tokens/seg en vivo. A la derecha, badges de estado
 * (thinking / agente) y la acción de limpiar el hilo. Números con `tabular-nums`.
 */
export function ChatHeader({
  sessionTitle,
  activeModel,
  isStreaming,
  liveTokensPerSecond,
  liveTokens,
  thinkingOn,
  agentMode,
  onClear,
  canClear,
}: Props) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] pb-4">
      <div className="flex min-w-0 flex-col gap-1">
        <h2 className="truncate text-subtitle text-[var(--color-ink-deep)]">
          {sessionTitle ?? "Playground"}
        </h2>
        {activeModel ? (
          <div className="flex items-center gap-2">
            <span
              aria-hidden
              className={cn(
                "size-1.5 rounded-[var(--radius-pill)]",
                activeModel.healthy && "anim-pulse-soft",
              )}
              style={{
                backgroundColor: activeModel.healthy
                  ? "var(--color-blue-flat)"
                  : "var(--color-error)",
              }}
            />
            <span className="font-mono text-body-sm text-[var(--color-ink)]">
              {activeModel.served_name}
            </span>
            <span className="text-caption text-[var(--color-ink-soft)]">
              {activeModel.role === "agent" ? "agente" : "conversacional"}
            </span>
          </div>
        ) : (
          <span className="text-caption text-[var(--color-ink-soft)]">Sin modelo seleccionado</span>
        )}
      </div>

      <div className="flex items-center gap-2">
        {isStreaming ? (
          <span className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--color-blue-flat)] px-3 py-1">
            <span
              aria-hidden
              className="anim-pulse-soft size-1.5 rounded-[var(--radius-pill)]"
              style={{ backgroundColor: "var(--color-blue-flat)" }}
            />
            <span className="text-caption tabular-nums text-[var(--color-ink)]">
              {liveTokensPerSecond.toFixed(1)} tok/s
            </span>
            <span className="text-caption tabular-nums text-[var(--color-ink-soft)]">
              {liveTokens} tok
            </span>
          </span>
        ) : null}

        {agentMode ? <StateBadge label="Agente" /> : null}
        {thinkingOn ? <StateBadge label="Thinking" /> : null}

        <button
          type="button"
          onClick={onClear}
          disabled={!canClear}
          className="rounded-[var(--radius-md)] px-3 py-1.5 text-button text-[var(--color-ink-soft)] transition-colors duration-[var(--duration-fast)] hover:bg-[var(--color-bg-soft)] hover:text-[var(--color-ink)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          Limpiar
        </button>
      </div>
    </header>
  );
}

/** Pill de estado neutro (thinking / agente). */
function StateBadge({ label }: { label: string }) {
  return (
    <span className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-2.5 py-1 text-caption text-[var(--color-ink-soft)]">
      {label}
    </span>
  );
}
