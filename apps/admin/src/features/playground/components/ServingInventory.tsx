import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import type { ServingModelOutT, ServingOutT } from "../schemas";

type Props = {
  serving: ServingOutT;
  className?: string;
};

/** Etiqueta humana del role del modelo (sin inglés crudo en la UI). */
const ROLE_LABEL: Record<ServingModelOutT["role"], string> = {
  conversational: "Conversacional",
  agent: "Agente",
};

/**
 * Banda 0 del Playground (ADR-018 §3): estado read-only del serving.
 *
 * Encabeza con un badge de backend que resume el estado en un golpe de vista
 * (decisión de marca: OK = **azul plano**, no verde; el panel no tiene token de
 * success ni de warning):
 *  - `is_real=false`            → pill de atención "Serving fake — sin generación
 *                                 real". El panel no tiene token ámbar/warning;
 *                                 el estado "atención" se pinta con los tokens de
 *                                 error (mismo criterio que `PerimeterBadge`),
 *                                 sin pulso para no leerse como caída.
 *  - `is_real ∧ serving_healthy`→ dot azul plano "Serving activo".
 *  - `is_real ∧ !healthy`       → borde error "Serving caído".
 *
 * Después una fila por modelo (served_name mono · role · max_model_len
 * tabular-nums · quant · tool_parser · dot healthy) y embedder/reranker en
 * caption host-less. Cero secretos (sin base_url, regla #4).
 */
export function ServingInventory({ serving, className }: Props) {
  return (
    <Card className={cn("flex flex-col gap-5", className)}>
      <header className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <p className="text-caption text-[var(--color-ink-soft)]">Serving</p>
          <h3 className="text-subtitle text-[var(--color-ink-deep)]">Inventario de modelos</h3>
        </div>
        <BackendBadge isReal={serving.is_real} healthy={serving.serving_healthy} />
      </header>

      <dl className="flex flex-col">
        {serving.models.map((model, i) => (
          <ModelRow key={model.key} model={model} last={i === serving.models.length - 1} />
        ))}
      </dl>

      <footer className="flex flex-wrap gap-x-6 gap-y-1 border-t border-[var(--color-border)] pt-4 text-caption text-[var(--color-ink-soft)]">
        <span>
          Embedder: <span className="tabular-nums text-[var(--color-ink)]">{serving.embedder}</span>
        </span>
        <span>
          Reranker: <span className="tabular-nums text-[var(--color-ink)]">{serving.reranker}</span>
        </span>
        <span>
          Timeout:{" "}
          <span className="tabular-nums text-[var(--color-ink)]">{serving.request_timeout_s}s</span>
        </span>
      </footer>
    </Card>
  );
}

/** Badge de estado del backend, color por estado (azul plano OK / atención / error). */
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
          Serving fake — sin generación real
        </span>
      </span>
    );
  }

  const statusVar = healthy ? "--color-blue-flat" : "--color-error";
  const label = healthy ? "Serving activo" : "Serving caído";
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
        {label}
      </span>
    </span>
  );
}

/** Fila de un modelo del catálogo. Hairline inferior salvo la última (`last`). */
function ModelRow({ model, last }: { model: ServingModelOutT; last: boolean }) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3",
        !last && "border-b border-[var(--color-border)]",
      )}
    >
      <div className="flex items-center gap-2">
        <span
          aria-hidden
          className={cn("size-2 shrink-0 rounded-[var(--radius-pill)]")}
          style={{
            backgroundColor: model.healthy ? "var(--color-blue-flat)" : "var(--color-ink-faint)",
          }}
        />
        <span className="font-mono text-body-sm text-[var(--color-ink)]">{model.served_name}</span>
        <span className="text-caption text-[var(--color-ink-soft)]">{ROLE_LABEL[model.role]}</span>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-[var(--color-ink-soft)]">
        <span>
          ctx <span className="tabular-nums text-[var(--color-ink)]">{model.max_model_len}</span>
        </span>
        <span className="text-[var(--color-ink)]">{model.quantization}</span>
        <span>{model.tool_parser}</span>
      </div>
    </div>
  );
}
