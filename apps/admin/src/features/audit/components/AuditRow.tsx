import type { CSSProperties } from "react";
import { Diamond } from "@/components/ui/Diamond";
import { ModeChip } from "@/components/ui/ModeChip";
import type { AdminAuditRowT, AuditOperationT, AuditTargetLayerT } from "@/features/audit/schemas";
import { cn } from "@/lib/cn";
import { relativeTime } from "@/lib/relativeTime";

/**
 * Color plano del chip por `operation` (blueprint §2.3): read = ink-soft (lectura
 * pasiva), write = azul (creación), update = violáceo (mutación), delete = error.
 * Todo por token — cero hex, cero gradiente. El chip lleva un punto de color +
 * label, no fondo saturado, para no competir con el `ModeChip` de la misma fila.
 */
const OPERATION_DOT: Record<AuditOperationT, string> = {
  read: "var(--color-ink-soft)",
  write: "var(--color-azul)",
  update: "var(--color-violaceo)",
  delete: "var(--color-error)",
};

const OPERATION_LABEL: Record<AuditOperationT, string> = {
  read: "Lectura",
  write: "Escritura",
  update: "Actualización",
  delete: "Borrado",
};

/** Color de capa del badge `target_layer` — reusa los alias semánticos del moat. */
const LAYER_VAR: Record<AuditTargetLayerT, string> = {
  semantic: "var(--layer-semantic)",
  episodic: "var(--layer-episodic)",
  procedural: "var(--layer-procedural)",
};

const LAYER_LABEL: Record<AuditTargetLayerT, string> = {
  semantic: "Semántica",
  episodic: "Episódica",
  procedural: "Procedural",
};

/**
 * Tiempo absoluto compacto (`19 jun 14:32`) para la columna de timestamp.
 * Tabular-nums obligatorio: la columna de tiempo es la que más se escanea
 * verticalmente, así que las cifras deben alinear. El relativo va de title
 * (tooltip nativo) para contexto sin ensuciar la grilla.
 */
const absFmt = new Intl.DateTimeFormat("es-AR", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/**
 * Chip plano de operación: punto de color + label. `aria-hidden` en el punto
 * (la palabra ya comunica la operación a lectores de pantalla).
 */
function OperationChip({ operation }: { operation: AuditOperationT }) {
  return (
    <span className="text-body-sm inline-flex items-center gap-2 text-[var(--color-ink)]">
      <span
        aria-hidden
        className="size-2 shrink-0 rounded-[var(--radius-pill)]"
        style={{ backgroundColor: OPERATION_DOT[operation] }}
      />
      {OPERATION_LABEL[operation]}
    </span>
  );
}

/**
 * Badge plano de capa: hairline del color de capa + label. Outline (no relleno)
 * para diferenciarse del `ModeChip` y mantener la fila liviana.
 */
function LayerBadge({ layer }: { layer: AuditTargetLayerT }) {
  return (
    <span
      className="text-caption inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] border px-2.5 py-0.5 text-[var(--color-ink-soft)]"
      style={{ borderColor: LAYER_VAR[layer] }}
    >
      <span
        aria-hidden
        className="size-1.5 shrink-0 rounded-[var(--radius-pill)]"
        style={{ backgroundColor: LAYER_VAR[layer] }}
      />
      {LAYER_LABEL[layer]}
    </span>
  );
}

type Props = {
  row: AdminAuditRowT;
  /** Índice de fila para el stagger de entrada (delay por `--stagger-index`). */
  staggerIndex?: number;
  className?: string;
};

/**
 * Fila editorial del audit log soberano (blueprint §2.3 + §3 F1.5).
 *
 * Render en grilla de 6 columnas (alineada con el header de `AuditTable` vía la
 * misma `grid-template-columns`). Hairline inferior (no caja, no zebra), hover
 * `bg-soft` sin scale (filas densas, §5 micro-interacciones).
 *
 * PRIVACIDAD: `AdminAuditRowT` no tiene `record_hash` ni `target_id` (omitidos en
 * el Zod). Acá no hay nada que ocultar en render porque esos campos directamente
 * no existen en el tipo — la columna "Origen" muestra modelo + tool, jamás el id
 * del registro tocado ni el hash de integridad.
 */
export function AuditRow({ row, staggerIndex = 0, className }: Props) {
  const created = new Date(row.created_at);
  const createdMs = created.getTime();

  return (
    <div
      style={{ "--stagger-index": staggerIndex } as CSSProperties}
      className={cn(
        "anim-stagger-up grid grid-cols-[8rem_9rem_8.5rem_minmax(0,1fr)_minmax(0,1fr)_3rem] items-center gap-4 border-b border-[var(--color-border)] px-4 py-3 transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:bg-[var(--color-bg-soft)]",
        className,
      )}
    >
      {/* Timestamp — tabular-nums, relativo en tooltip */}
      <time
        dateTime={row.created_at}
        title={relativeTime(createdMs)}
        className="text-body-sm tabular-nums text-[var(--color-ink-soft)]"
      >
        {absFmt.format(created)}
      </time>

      {/* Operación */}
      <OperationChip operation={row.operation} />

      {/* Capa objetivo */}
      <div>
        <LayerBadge layer={row.target_layer} />
      </div>

      {/* Modo de origen */}
      <div className="min-w-0">
        {row.origin_mode ? (
          <ModeChip modeId={row.origin_mode} size="sm" />
        ) : (
          <span className="text-body-sm text-[var(--color-ink-muted)]">—</span>
        )}
      </div>

      {/* Origen: modelo + tool (NUNCA target_id ni record_hash) */}
      <div className="text-body-sm min-w-0 truncate text-[var(--color-ink-soft)]">
        {row.origin_model ? (
          <span className="text-[var(--color-ink)] uppercase">{row.origin_model}</span>
        ) : (
          <span className="text-[var(--color-ink-muted)]">sin modelo</span>
        )}
        {row.origin_tool ? (
          <span className="text-[var(--color-ink-muted)]"> · {row.origin_tool}</span>
        ) : null}
      </div>

      {/* Sensible: Diamond lleno si toca dato sensible */}
      <div className="flex justify-center">
        {row.sensitive ? (
          <span
            title="Operación sobre dato sensible"
            className="inline-flex items-center justify-center"
          >
            <Diamond size={10} color="var(--color-error)" />
            <span className="sr-only">Operación sobre dato sensible</span>
          </span>
        ) : (
          <Diamond size={8} color="var(--color-ink-faint)" variant="outline" />
        )}
      </div>
    </div>
  );
}
