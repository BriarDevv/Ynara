"use client";

import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import type { ServingModelOutT, ServingOutT } from "../schemas";

type Props = {
  serving: ServingOutT;
  /** `served_name` del modelo activo (el elegido en los controles). */
  activeModel: string;
  className?: string;
};

const ROLE_LABEL: Record<ServingModelOutT["role"], string> = {
  conversational: "Conversacional",
  agent: "Agente",
};

/**
 * Panel "qué IA está activa" (riel derecho del Playground rediseñado).
 *
 * Responde de un vistazo: ¿el serving es real?, ¿qué modelos hay y cuáles están
 * sanos (gemma4/qwen)?, ¿cuál está activo en el turno? El dot late
 * (`anim-pulse-soft`) cuando el modelo está sano; el activo lleva un anillo azul
 * de marca. Sin verde/ámbar (decisión de marca: OK = azul plano). Sin secretos
 * (sin base_url, regla #4). Embedder/reranker al pie.
 */
export function ModelHealthPanel({ serving, activeModel, className }: Props) {
  return (
    <Card className={cn("flex flex-col gap-4", className)}>
      <header className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="text-caption text-[var(--color-ink-soft)]">Serving</p>
          <h3 className="text-subtitle text-[var(--color-ink-deep)]">IA activa</h3>
        </div>
        <BackendBadge isReal={serving.is_real} healthy={serving.serving_healthy} />
      </header>

      <ul className="flex flex-col gap-2">
        {serving.models.map((model) => (
          <ModelRow key={model.key} model={model} active={model.served_name === activeModel} />
        ))}
      </ul>

      <footer className="flex flex-wrap gap-x-5 gap-y-1 border-t border-[var(--color-border)] pt-3 text-caption text-[var(--color-ink-soft)]">
        <span>
          Embedder <span className="tabular-nums text-[var(--color-ink)]">{serving.embedder}</span>
        </span>
        <span>
          Reranker <span className="tabular-nums text-[var(--color-ink)]">{serving.reranker}</span>
        </span>
      </footer>
    </Card>
  );
}

/** Badge de backend: azul plano OK / atención (fake) / error (caído). */
function BackendBadge({ isReal, healthy }: { isReal: boolean; healthy: boolean }) {
  if (!isReal) {
    return (
      <span className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--color-error)] bg-[var(--color-error-soft)] px-3 py-1">
        <span
          aria-hidden
          className="size-2 rounded-[var(--radius-pill)]"
          style={{ backgroundColor: "var(--color-error)" }}
        />
        <span className="text-caption" style={{ color: "var(--color-error)" }}>
          Serving fake
        </span>
      </span>
    );
  }
  const statusVar = healthy ? "--color-blue-flat" : "--color-error";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-[var(--radius-pill)] border px-3 py-1",
        healthy ? "border-[var(--color-border)]" : "border-[var(--color-error)]",
      )}
    >
      <span
        aria-hidden
        className={cn("size-2 rounded-[var(--radius-pill)]", healthy && "anim-pulse-soft")}
        style={{ backgroundColor: `var(${statusVar})` }}
      />
      <span className="text-caption" style={{ color: `var(${statusVar})` }}>
        {healthy ? "Serving activo" : "Serving caído"}
      </span>
    </span>
  );
}

/** Fila de un modelo: dot de salud + served_name + role + marca de activo. */
function ModelRow({ model, active }: { model: ServingModelOutT; active: boolean }) {
  return (
    <li
      className={cn(
        "flex items-center justify-between gap-3 rounded-[var(--radius-md)] border px-3 py-2 transition-colors duration-[var(--duration-fast)]",
        active
          ? "border-[var(--color-blue-flat)] bg-[var(--color-bg-soft)]"
          : "border-[var(--color-border)]",
      )}
    >
      <div className="flex items-center gap-2.5">
        <span
          aria-hidden
          className={cn(
            "size-2 shrink-0 rounded-[var(--radius-pill)]",
            model.healthy && "anim-pulse-soft",
          )}
          style={{
            backgroundColor: model.healthy ? "var(--color-blue-flat)" : "var(--color-ink-faint)",
          }}
        />
        <span className="flex flex-col">
          <span className="font-mono text-body-sm text-[var(--color-ink)]">
            {model.served_name}
          </span>
          <span className="text-caption text-[var(--color-ink-soft)]">
            {ROLE_LABEL[model.role]}
            {model.healthy ? "" : " · caído"}
          </span>
        </span>
      </div>
      {active ? (
        <span className="rounded-[var(--radius-pill)] bg-[var(--color-blue-flat)] px-2 py-0.5 text-caption text-[var(--color-on-dark)]">
          Activo
        </span>
      ) : null}
    </li>
  );
}
