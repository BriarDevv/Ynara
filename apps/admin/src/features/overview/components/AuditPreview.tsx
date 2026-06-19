"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import { Card } from "@/components/ui/Card";
import { Diamond } from "@/components/ui/Diamond";
import { ModeChip } from "@/components/ui/ModeChip";
import type { AdminOverviewOutT } from "@/features/overview/schemas";
import { cn } from "@/lib/cn";
import { relativeTime } from "@/lib/relativeTime";

type Row = AdminOverviewOutT["audit_preview"][number];
type Operation = Row["operation"];
type TargetLayer = Row["target_layer"];

type Props = {
  /** Hasta 6 filas exponibles del audit log (sin hash ni contenido). */
  rows: AdminOverviewOutT["audit_preview"];
  /** Índice para la cascada de entrada de las bandas del main. */
  staggerIndex?: number;
  className?: string;
};

/** Etiqueta humana de cada operación. */
const OPERATION_LABEL: Record<Operation, string> = {
  read: "Lectura",
  write: "Escritura",
  update: "Actualización",
  delete: "Borrado",
};

/**
 * Color plano del chip de operación (blueprint §2.3): lectura neutra, escritura
 * azul de marca, actualización violácea, borrado error. Tokens, cero hex.
 */
const OPERATION_COLOR: Record<Operation, string> = {
  read: "var(--color-ink-soft)",
  write: "var(--color-azul)",
  update: "var(--color-violaceo)",
  delete: "var(--color-error)",
};

/** Etiqueta humana de la capa del moat objetivo. */
const LAYER_LABEL: Record<TargetLayer, string> = {
  semantic: "Semántica",
  episodic: "Episódica",
  procedural: "Procedural",
};

/**
 * Preview de auditoría del Overview (blueprint §3 banda 4): las 6 filas más
 * recientes del audit log + link a la vista completa. Filas separadas por
 * hairlines (sin cajas ni zebra, estilo editorial), tiempos en `tabular-nums`,
 * chip plano por operación, badge por capa, `ModeChip` por modo de origen y un
 * `Diamond` lleno cuando la operación es sensible.
 *
 * Soberanía: estas filas traen solo campos exponibles — nunca `record_hash`,
 * `target_id` ni contenido descifrado (omitidos ya en el contrato Zod).
 */
export function AuditPreview({ rows, staggerIndex = 0, className }: Props) {
  return (
    <Card
      className={cn("anim-stagger-up flex flex-col gap-4", className)}
      style={{ "--stagger-index": staggerIndex } as CSSProperties}
    >
      <header className="flex items-baseline justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-subtitle text-[var(--color-ink-deep)]">Auditoría reciente</h2>
          <p className="text-caption text-[var(--color-ink-muted)]">
            Vista soberana — sin hash de integridad ni contenido descifrado.
          </p>
        </div>
        <Link
          href="/audit"
          className="shrink-0 text-body-sm text-[var(--color-accent)] underline underline-offset-4 decoration-[var(--color-ink-faint)] hover:decoration-[var(--color-accent)]"
        >
          Ver todo
        </Link>
      </header>

      {rows.length === 0 ? (
        <p className="text-body-sm text-[var(--color-ink-soft)]">Sin eventos en el rango.</p>
      ) : (
        <ul className="flex flex-col">
          {rows.map((row) => {
            const ts = Date.parse(row.created_at);
            const when = Number.isFinite(ts) ? relativeTime(ts) : row.created_at;
            return (
              <li
                key={row.id}
                className="flex items-center gap-3 border-t border-[var(--color-border)] py-3 first:border-t-0"
              >
                {/* Marca de sensibilidad: diamante lleno solo si la fila es sensible. */}
                <span className="flex w-3 shrink-0 justify-center">
                  {row.sensitive ? (
                    <Diamond size={8} color="var(--color-error)" />
                  ) : (
                    <span
                      aria-hidden
                      className="block h-1 w-1 rounded-full bg-[var(--color-ink-faint)]"
                    />
                  )}
                </span>

                {/* Operación: dot + label, color plano por tipo. */}
                <span className="inline-flex w-28 shrink-0 items-center gap-2">
                  <span
                    aria-hidden
                    className="h-1.5 w-1.5 shrink-0 rounded-[var(--radius-pill)]"
                    style={{ backgroundColor: OPERATION_COLOR[row.operation] }}
                  />
                  <span className="text-body-sm" style={{ color: OPERATION_COLOR[row.operation] }}>
                    {OPERATION_LABEL[row.operation]}
                  </span>
                </span>

                {/* Capa del moat objetivo. */}
                <span className="w-28 shrink-0 text-body-sm text-[var(--color-ink-soft)]">
                  {LAYER_LABEL[row.target_layer]}
                </span>

                {/* Modo de origen (puede ser nulo: operación de sistema). */}
                <span className="min-w-0 flex-1">
                  {row.origin_mode ? (
                    <ModeChip modeId={row.origin_mode} size="sm" variant="soft" />
                  ) : (
                    <span className="text-caption text-[var(--color-ink-muted)]">Sistema</span>
                  )}
                </span>

                {/* Tiempo relativo, tabular-nums, alineado a la derecha. */}
                <time
                  dateTime={row.created_at}
                  className="shrink-0 text-caption tabular-nums text-[var(--color-ink-muted)]"
                >
                  {when}
                </time>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
