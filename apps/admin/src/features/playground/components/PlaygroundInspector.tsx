"use client";

import { Card } from "@/components/ui/Card";
import { Diamond } from "@/components/ui/Diamond";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { cn } from "@/lib/cn";
import type {
  InspectorStep,
  InspectorStepStatus,
  InspectorTrace,
  ToolCallTrace,
} from "../inspector/trace";

type Props = {
  /**
   * Modelo de vista ya derivado por `buildTrace` / `buildAgentTrace` en el Screen.
   * El inspector no sabe si el resultado es de probe o de agente: solo consume la
   * forma estable `InspectorTrace`.
   */
  trace: InspectorTrace;
  /** Si hubo un turno (mensaje enviado): gatea el empty-state inicial. */
  hasTurn: boolean;
  className?: string;
};

/**
 * Sidebar inspector del Playground (blueprint §4 — Fase A + Fase B).
 *
 * Renderiza el lifecycle del request en tres secciones verticales:
 *  1. **Timeline** — nodos request/thinking/completion (o "agent" en vuelo) con
 *     `Diamond` coloreado por estado y hairline conector. Pulsante en `pending`.
 *  2. **ThinkingBlock** — `<details>/<summary>` colapsable con el `<think>…</think>`
 *     separado; gating triple (sin thinking / sin texto / con texto).
 *  3. **ToolCallCards** (Fase B) — una sección por tool-call observada del loop
 *     de agente: header `font-mono` con nombre + iter; args y result en `<details>`
 *     `font-mono` nativos. Error/`unknown_tool` en `bg-error-soft`.
 *
 * Paleta acotada al design system: OK = `--color-blue-flat`, error =
 * `--color-error`, thinking teñido `--color-violeta`. Sin verde/ámbar, sin
 * gradiente, sin hex. Números con `tabular-nums`.
 *
 * Sin turno todavía → `EmptyStateCard`. El inspector es 100% presentacional:
 * recibe `InspectorTrace` ya derivada del Screen (cero lógica de mapeo acá).
 */
export function PlaygroundInspector({ trace, hasTurn, className }: Props) {
  return (
    <Card className={cn("flex flex-col gap-5", className)}>
      <header className="flex flex-col gap-1">
        <p className="text-caption text-[var(--color-ink-soft)]">Inspector</p>
        <h3 className="text-subtitle text-[var(--color-ink-deep)]">Trace del request</h3>
      </header>

      {!hasTurn ? (
        <EmptyStateCard
          title="Sin turno todavía."
          hint="Mandá un mensaje y el lifecycle del request aparece acá."
        />
      ) : (
        <div className="flex flex-col gap-5">
          <Timeline steps={trace.steps} />
          <ThinkingBlock trace={trace} />
          {trace.tools && trace.tools.length > 0 ? <ToolCallCards tools={trace.tools} /> : null}
        </div>
      )}
    </Card>
  );
}

/** Color de marca por estado del nodo (sin verde/ámbar: solo azul plano / error). */
const STATUS_COLOR: Record<InspectorStepStatus, string> = {
  ok: "var(--color-blue-flat)",
  error: "var(--color-error)",
  pending: "var(--color-blue-flat)",
};

/**
 * Timeline vertical (`<ol>`) con un `Diamond` por nodo sobre un hairline
 * `border-l`. El step en curso (`pending`) late con `.anim-pulse-soft`.
 */
function Timeline({ steps }: { steps: InspectorStep[] }) {
  if (steps.length === 0) {
    return <p className="text-body-sm text-[var(--color-ink-soft)]">Sin pasos registrados.</p>;
  }

  // El timeline es un set fijo de nodos por turno (`request`/`thinking`/
  // `completion`): el `name` es único y estable, así que sirve de key sin
  // recurrir al índice del array.
  return (
    <ol className="flex flex-col">
      {steps.map((step, i) => (
        <TimelineNode key={step.name} step={step} isLast={i === steps.length - 1} />
      ))}
    </ol>
  );
}

/**
 * Un nodo del timeline: el `Diamond` coloreado por estado y el hairline que lo
 * conecta con el siguiente (salvo el último). Detalle + duración a la derecha.
 */
function TimelineNode({ step, isLast }: { step: InspectorStep; isLast: boolean }) {
  const color = STATUS_COLOR[step.status];
  return (
    <li className="flex gap-3">
      {/* Riel: diamante + hairline vertical hasta el próximo nodo. */}
      <div className="flex flex-col items-center">
        <Diamond
          size={10}
          color={color}
          className={cn("mt-1", step.status === "pending" && "anim-pulse-soft")}
        />
        {!isLast ? (
          <span aria-hidden className="w-px flex-1 border-l border-[var(--color-border)]" />
        ) : null}
      </div>

      {/* Contenido: nombre del paso + detalle + duración (tabular-nums). */}
      <div className={cn("flex flex-1 flex-col gap-0.5", isLast ? "pb-0" : "pb-4")}>
        <span className="flex items-center justify-between gap-3">
          <span className="text-body-sm text-[var(--color-ink)]">{step.name}</span>
          {step.durationMs != null ? (
            <span className="text-caption tabular-nums text-[var(--color-ink-soft)]">
              {Math.round(step.durationMs)}ms
            </span>
          ) : null}
        </span>
        <span className="text-caption text-[var(--color-ink-soft)]">{step.detail}</span>
      </div>
    </li>
  );
}

/**
 * Bloque de thinking colapsable (`<details>/<summary>` nativo, a11y gratis).
 *
 * Gating (blueprint §4):
 *  - sin thinking aplicado → no se renderiza nada.
 *  - `thinkingUsed && !thinkingText` → nota "aplicado, no expuesto" (estática).
 *  - con texto → `<details>` con el `<think>` en `font-mono whitespace-pre-wrap`
 *    teñido `--color-violeta`; el chevron rota con `group-open:rotate-90`.
 */
function ThinkingBlock({ trace }: { trace: InspectorTrace }) {
  if (!trace.thinkingUsed) return null;

  if (!trace.thinkingText) {
    return (
      <p className="text-caption text-[var(--color-ink-soft)]">Thinking aplicado (no expuesto).</p>
    );
  }

  return (
    <details className="group flex flex-col gap-2">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-body-sm text-[var(--color-ink)]">
        <span
          aria-hidden
          className="inline-block text-[var(--color-violeta)] transition-transform duration-[var(--duration-fast)] group-open:rotate-90"
        >
          ›
        </span>
        Thinking del modelo
      </summary>
      <pre className="mt-1 whitespace-pre-wrap rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] px-3 py-2 font-mono text-caption text-[var(--color-violeta)]">
        {trace.thinkingText}
      </pre>
    </details>
  );
}

/**
 * Sección de tool-call cards (Fase B, blueprint §4).
 *
 * Una card por cada tool-call observada del loop: header `font-mono` con nombre
 * + fondo `bg-error-soft` si es error/`unknown_tool`; args y result en `<details>`
 * `font-mono` nativos. El número de tools lleva `tabular-nums`.
 */
function ToolCallCards({ tools }: { tools: ToolCallTrace[] }) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-caption text-[var(--color-ink-soft)]">
        Tools observadas
        {/* Número de tool-calls: tabular-nums para que no "baile" con más items. */}
        <span className="ml-1 tabular-nums">({tools.length})</span>
      </p>
      {tools.map((tool, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: las tool-calls son una lista ordenada estable por turno; el id del modelo puede repetirse en loops multi-iteración.
        <ToolCallCard key={`${tool.id}-${i}`} tool={tool} iter={i + 1} total={tools.length} />
      ))}
    </div>
  );
}

/**
 * Una card de tool-call: header `font-mono` con nombre + `iter n/total` +
 * indicador de error; `arguments` y `result` en `<details>` `font-mono`.
 * El fondo del header es `bg-error-soft` cuando el result es error/`unknown_tool`.
 */
function ToolCallCard({ tool, iter, total }: { tool: ToolCallTrace; iter: number; total: number }) {
  return (
    <div className="flex flex-col overflow-hidden rounded-[var(--radius-md)] border border-[var(--color-border)]">
      {/* Header: nombre de la tool + iter n/total (tabular-nums). */}
      <div
        className={cn(
          "flex items-center justify-between gap-3 px-3 py-2",
          tool.isError ? "bg-[var(--color-error-soft)]" : "bg-[var(--color-bg-soft)]",
        )}
      >
        <span
          className={cn(
            "font-mono text-caption",
            tool.isError ? "text-[var(--color-error)]" : "text-[var(--color-ink)]",
          )}
        >
          {tool.name}
        </span>
        <span className="shrink-0 font-mono text-caption tabular-nums text-[var(--color-ink-soft)]">
          {iter}/{total}
        </span>
      </div>

      {/* Args + result en details colapsables (font-mono). */}
      <div className="flex flex-col divide-y divide-[var(--color-border)]">
        <ToolDetail summary="arguments" content={tool.arguments} />
        <ToolDetail summary="result" content={tool.result} isError={tool.isError} />
      </div>
    </div>
  );
}

/**
 * Un `<details>/<summary>` de tool-call (`arguments` o `result`). El contenido
 * va en `font-mono whitespace-pre-wrap` para preservar el JSON crudo del backend.
 */
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
    <details className="group px-3 py-2">
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
          "mt-1.5 whitespace-pre-wrap rounded-[var(--radius-sm)] px-2 py-1.5 font-mono text-caption",
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
