"use client";

import { Card } from "@/components/ui/Card";
import { Diamond } from "@/components/ui/Diamond";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { cn } from "@/lib/cn";
import {
  buildTrace,
  type InspectorStep,
  type InspectorStepStatus,
  type InspectorTrace,
} from "../inspector/trace";
import type { PlaygroundOutT } from "../schemas";
import type { PlaygroundConfig } from "./PlaygroundControls";

type Props = {
  /** Config del turno (modelo + thinking elegido), para el trace en vuelo. */
  config: PlaygroundConfig;
  /** La respuesta del turno (null mientras no llegó / sin turno). */
  result: PlaygroundOutT | null;
  /** True mientras la mutation está en vuelo (step en curso pulsante). */
  isPending: boolean;
  /** Si hubo un turno (mensaje enviado): gatea el empty-state inicial. */
  hasTurn: boolean;
  className?: string;
};

/**
 * Sidebar inspector del Playground (Fase A del trace, blueprint §4).
 *
 * Espeja el lifecycle del request en un panel sticky al costado del chat: un
 * **timeline** vertical de pasos (request → thinking → completion) y el
 * **thinking** del modelo en un bloque colapsable. Todo derivado de
 * `PlaygroundOut` vía la función pura `buildTrace` (cero lógica de mapeo acá).
 *
 * Paleta acotada al design system: OK = `--color-blue-flat`, error =
 * `--color-error`, thinking teñido `--color-violeta`. Sin verde/ámbar (no hay
 * tokens), sin gradiente, sin hex. Números con `tabular-nums`.
 *
 * Sin turno todavía → `EmptyStateCard`. La caja de tool-calls (Fase B) no se
 * pinta en Fase A aunque `InspectorTrace.tools` ya exista en el tipo.
 */
export function PlaygroundInspector({ config, result, isPending, hasTurn, className }: Props) {
  const trace = buildTrace(config, result, { isPending });

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
