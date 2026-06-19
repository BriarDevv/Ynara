import type { ReactNode } from "react";
import { Card } from "@/components/ui/Card";
import { ModeChip } from "@/components/ui/ModeChip";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
import { cn } from "@/lib/cn";

type Props = {
  /** Modelos LLM cargados (p.ej. `["gemma", "qwen"]`). */
  models: string[];
  /** Modos del enum `Mode` del backend (strings; se chipean si son válidos). */
  modes: string[];
  /** Revisión de Alembic en cabeza (último migrado), p.ej. `20260615_0200`. */
  schemaHead: string;
  /** Modelo de embeddings cargado, p.ej. `bge-m3 (1024d)`. */
  embedder: string;
  /** Reranker cargado, p.ej. `bge-reranker-v2-m3`. */
  reranker: string;
  /** Versión de build del panel (`admin@0.1.0`). */
  buildVersion: string;
  className?: string;
};

/** Set de modos canónicos válidos, para chipear solo lo que el DS conoce. */
const KNOWN_MODES = new Set<string>(Object.keys(MODE_BY_ID));

/**
 * Inventario de runtime/config NO sensible (blueprint §2.3 / §3 F1.6).
 *
 * Tabla de definición plana (hairlines entre filas, sin zebra, sin cajas) con la
 * configuración que el panel puede exponer sin riesgo: modelos LLM, los 5 modos,
 * cabeza del schema (Alembic), embedder/reranker y versión de build. Cero datos
 * de negocio ni de usuario.
 *
 * Los valores técnicos (versión de schema, build) van con `tabular-nums` para
 * que las revisiones alineen. Los modos conocidos se renderizan con `ModeChip`
 * (sus tints oficiales); cualquier string no reconocido cae a label plano —
 * honestidad: no fingimos que un modo desconocido es uno de los cinco.
 */
export function RuntimeInventory({
  models,
  modes,
  schemaHead,
  embedder,
  reranker,
  buildVersion,
  className,
}: Props) {
  return (
    <Card className={cn("flex flex-col gap-5", className)}>
      <header className="flex flex-col gap-1">
        <p className="text-caption text-[var(--color-ink-soft)]">Configuración</p>
        <h3 className="text-subtitle text-[var(--color-ink-deep)]">Inventario de runtime</h3>
      </header>

      <dl className="flex flex-col">
        <Row label="Modelos LLM">
          <div className="flex flex-wrap justify-end gap-2">
            {models.map((m) => (
              <span
                key={m}
                className="rounded-[var(--radius-pill)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1 text-caption text-[var(--color-ink)]"
              >
                {m}
              </span>
            ))}
          </div>
        </Row>

        <Row label="Modos">
          <div className="flex flex-wrap justify-end gap-2">
            {modes.map((m) =>
              KNOWN_MODES.has(m) ? (
                <ModeChip key={m} modeId={m as ModeId} size="sm" />
              ) : (
                <span
                  key={m}
                  className="rounded-[var(--radius-pill)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1 text-caption text-[var(--color-ink-soft)]"
                >
                  {m}
                </span>
              ),
            )}
          </div>
        </Row>

        <Row label="Schema head (Alembic)">
          <span className="text-body-sm tabular-nums text-[var(--color-ink)]">{schemaHead}</span>
        </Row>

        <Row label="Embedder">
          <span className="text-body-sm tabular-nums text-[var(--color-ink)]">{embedder}</span>
        </Row>

        <Row label="Reranker">
          <span className="text-body-sm tabular-nums text-[var(--color-ink)]">{reranker}</span>
        </Row>

        <Row label="Build" last>
          <span className="text-body-sm tabular-nums text-[var(--color-ink)]">{buildVersion}</span>
        </Row>
      </dl>
    </Card>
  );
}

/**
 * Fila de la tabla de definición: término a la izquierda (`ink-soft`), valor a
 * la derecha. Hairline inferior salvo la última (`last`). Sin cajas ni zebra,
 * mismo idioma que la `AuditTable`.
 */
function Row({
  label,
  children,
  last = false,
}: {
  label: string;
  children: ReactNode;
  last?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-6 py-3",
        !last && "border-b border-[var(--color-border)]",
      )}
    >
      <dt className="text-body-sm text-[var(--color-ink-soft)]">{label}</dt>
      <dd className="flex min-w-0 items-center">{children}</dd>
    </div>
  );
}
