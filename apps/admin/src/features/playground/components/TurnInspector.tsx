"use client";

import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import type { ChatTurn } from "@/stores/playgroundSessions";
import type { LiveTurn } from "../hooks/usePlaygroundStream";
import type { ToolCallOutT } from "../schemas";

type Props = {
  /** Último turno assistant de la sesión (persistido), o `null`. */
  turn: ChatTurn | null;
  /** Turno en vuelo (streaming): pisa al persistido mientras corre. */
  live: LiveTurn;
  className?: string;
};

/**
 * Inspector del turno (riel derecho). Muestra las métricas del último turno (o
 * del que está en vuelo) como lista de stats `tabular-nums`, y —en modo agente—
 * las tool-calls observadas del loop de qwen (incluidas las `memory.*`, que caen
 * en `unknown_tool` por construcción: cero efecto sobre la memoria real, ADR-019).
 *
 * El razonamiento (`thinking`) se ve en la propia burbuja del chat; acá el foco
 * es métrica + acciones. Sin turno → empty state inline.
 */
export function TurnInspector({ turn, live, className }: Props) {
  const streaming = live.phase === "streaming";

  return (
    <Card className={cn("flex flex-col gap-4", className)}>
      <header className="flex flex-col gap-1">
        <p className="text-caption text-[var(--color-ink-soft)]">Inspector</p>
        <h3 className="text-subtitle text-[var(--color-ink-deep)]">
          {streaming ? "Turno en vivo" : "Último turno"}
        </h3>
      </header>

      {streaming ? (
        <Stats
          rows={[
            ["tok/s", `${live.tokensPerSecond.toFixed(1)}`],
            ["tokens", `${live.completionTokens}`],
            ["estado", "generando…"],
          ]}
        />
      ) : turn && turn.status === "ok" ? (
        <>
          <Stats rows={turnStats(turn)} />
          {turn.agent && turn.actions && turn.actions.length > 0 ? (
            <ToolCalls actions={turn.actions} />
          ) : null}
        </>
      ) : (
        <p className="text-body-sm text-[var(--color-ink-soft)]">
          Sin turno todavía. Mandá un mensaje y las métricas aparecen acá.
        </p>
      )}
    </Card>
  );
}

/** Filas de stats del turno persistido. */
function turnStats(turn: ChatTurn): [string, string][] {
  if (turn.agent) {
    return [
      ["modelo", turn.model ?? "—"],
      ["cierre", turn.finishReason ?? "—"],
      ["tools", `${turn.actions?.length ?? 0}`],
    ];
  }
  return [
    ["modelo", turn.model ?? "—"],
    ["cierre", turn.finishReason ?? "—"],
    ["tokens", `${turn.completionTokens ?? 0}`],
    ["tok/s", turn.tokensPerSecond != null ? turn.tokensPerSecond.toFixed(1) : "—"],
    ["latencia", turn.latencyMs != null ? `${Math.round(turn.latencyMs)}ms` : "—"],
    ["thinking", turn.thinkingUsed ? "on" : "off"],
  ];
}

/** Lista de stats label/valor. Todo número con `tabular-nums`. */
function Stats({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="flex flex-col">
      {rows.map(([label, value], i) => (
        <div
          key={label}
          className={cn(
            "flex items-center justify-between gap-4 py-2",
            i < rows.length - 1 && "border-b border-[var(--color-border)]",
          )}
        >
          <dt className="text-caption text-[var(--color-ink-soft)]">{label}</dt>
          <dd className="tabular-nums text-body-sm text-[var(--color-ink)]">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Tool-calls observadas del loop agente (qwen). `memory.*` → unknown_tool. */
function ToolCalls({ actions }: { actions: ToolCallOutT[] }) {
  return (
    <div className="flex flex-col gap-3 border-t border-[var(--color-border)] pt-4">
      <p className="text-caption text-[var(--color-ink-soft)]">
        Tools observadas <span className="tabular-nums">({actions.length})</span>
      </p>
      {actions.map((action, i) => {
        const isError =
          action.result.toLowerCase().includes("unknown_tool") ||
          action.result.toLowerCase().includes("error");
        return (
          <div
            // biome-ignore lint/suspicious/noArrayIndexKey: lista ordenada estable por turno; el id puede repetirse entre iteraciones del loop.
            key={`${action.id}-${i}`}
            className="flex flex-col overflow-hidden rounded-[var(--radius-md)] border border-[var(--color-border)]"
          >
            <div
              className={cn(
                "flex items-center justify-between gap-3 px-3 py-2",
                isError ? "bg-[var(--color-error-soft)]" : "bg-[var(--color-bg-soft)]",
              )}
            >
              <span
                className={cn(
                  "font-mono text-caption",
                  isError ? "text-[var(--color-error)]" : "text-[var(--color-ink)]",
                )}
              >
                {action.name}
              </span>
              <span className="shrink-0 font-mono text-caption tabular-nums text-[var(--color-ink-soft)]">
                {i + 1}/{actions.length}
              </span>
            </div>
            <ToolDetail summary="arguments" content={action.arguments} />
            <ToolDetail summary="result" content={action.result} isError={isError} />
          </div>
        );
      })}
    </div>
  );
}

/** `<details>` de una tool-call (`arguments`/`result`) en `font-mono`. */
function ToolDetail({
  summary,
  content,
  isError = false,
}: {
  summary: string;
  content: string;
  isError?: boolean;
}) {
  return (
    <details className="group border-t border-[var(--color-border)] px-3 py-2">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-caption text-[var(--color-ink-soft)]">
        <span
          aria-hidden
          className="inline-block transition-transform duration-[var(--duration-fast)] group-open:rotate-90"
        >
          ›
        </span>
        <span className="font-mono">{summary}</span>
      </summary>
      <pre
        className={cn(
          "mt-1.5 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-[var(--radius-sm)] px-2 py-1.5 font-mono text-caption scrollbar-none",
          isError
            ? "bg-[var(--color-error-soft)] text-[var(--color-error)]"
            : "bg-[var(--color-bg-soft)] text-[var(--color-ink-soft)]",
        )}
      >
        {content}
      </pre>
    </details>
  );
}
