"use client";

import { type ReactNode, useId } from "react";
import { Button } from "@/components/ui/Button";
import { ModeChip } from "@/components/ui/ModeChip";
import { MODES } from "@/components/ui/modes";
import {
  type AuditFilterState,
  type AuditOperationT,
  type AuditOriginModelT,
  type AuditTargetLayerT,
  EMPTY_AUDIT_FILTERS,
} from "@/features/audit/schemas";
import { cn } from "@/lib/cn";

/**
 * Opciones de cada select. El valor `""` representa "todos" (= `null` en el
 * estado): el `<select>` no admite `null`, así que la conversión vive en los
 * handlers (`value || null`). Mantener las etiquetas acá, no inline, para que el
 * orden y los textos sean una sola fuente.
 */
const LAYER_OPTIONS: ReadonlyArray<{ value: AuditTargetLayerT; label: string }> = [
  { value: "semantic", label: "Semántica" },
  { value: "episodic", label: "Episódica" },
  { value: "procedural", label: "Procedural" },
];

const MODEL_OPTIONS: ReadonlyArray<{ value: AuditOriginModelT; label: string }> = [
  { value: "gemma", label: "Gemma" },
  { value: "qwen", label: "Qwen" },
];

const OPERATION_OPTIONS: ReadonlyArray<{ value: AuditOperationT; label: string }> = [
  { value: "read", label: "Lectura" },
  { value: "write", label: "Escritura" },
  { value: "update", label: "Actualización" },
  { value: "delete", label: "Borrado" },
];

const SELECT_CLASS =
  "text-body-sm h-9 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 text-[var(--color-ink)] transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:border-[var(--color-border-strong)]";

/**
 * Botón-toggle plano para una opción de filtro (operación / sensible). Reusa el
 * patrón de `selected-ring` del DS para el estado activo. No es radiogroup
 * porque acá la deselección (volver a "todos") es válida — clic en el activo lo
 * apaga.
 */
function ToggleChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "text-body-sm rounded-[var(--radius-pill)] border px-3 py-1.5 transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
        active
          ? "border-[var(--color-selected-ring)] bg-[var(--color-bg-soft)] text-[var(--color-ink)]"
          : "border-[var(--color-border)] text-[var(--color-ink-soft)] hover:border-[var(--color-border-strong)] hover:text-[var(--color-ink)]",
      )}
    >
      {children}
    </button>
  );
}

/** Bloque etiquetado de un grupo de filtros (label caption + control). */
function FilterField({
  label,
  children,
  htmlFor,
}: {
  label: string;
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={htmlFor} className="text-caption text-[var(--color-ink-soft)]">
        {label}
      </label>
      {children}
    </div>
  );
}

type Props = {
  value: AuditFilterState;
  onChange: (filters: AuditFilterState) => void;
  className?: string;
};

/**
 * Filtros de la tabla soberana (blueprint §2.3 + §3 F1.5).
 *
 * Sticky bajo el topbar (`z-sticky`) para que los filtros queden a mano mientras
 * se scrollea la tabla. Expone SOLO campos publicables: operación (toggles),
 * capa objetivo (select), modo de origen (toggles `ModeChip`), modelo de origen
 * (select) y sensibilidad (tri-estado: todos / sensibles / no sensibles). El
 * rango temporal NO está acá: lo hereda del topbar global.
 *
 * Cada `onChange` reemplaza el estado completo (inmutable) y resetea
 * implícitamente la paginación en el page (que vuelve a página 0 al cambiar
 * filtros). Clic en una opción ya activa la apaga (vuelve a "todos").
 */
export function AuditFilters({ value, onChange, className }: Props) {
  const layerId = useId();
  const modelId = useId();

  const patch = (next: Partial<AuditFilterState>) => onChange({ ...value, ...next });
  const isDirty =
    value.operation !== null ||
    value.targetLayer !== null ||
    value.originMode !== null ||
    value.originModel !== null ||
    value.sensitive !== null;

  return (
    <div
      className={cn(
        "sticky top-0 z-[var(--z-sticky)] flex flex-col gap-4 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-glass)] px-5 py-4 backdrop-blur",
        className,
      )}
    >
      <div className="flex flex-wrap items-start gap-x-8 gap-y-4">
        {/* Operación — toggles */}
        <FilterField label="Operación">
          <div className="flex flex-wrap gap-2">
            {OPERATION_OPTIONS.map((opt) => (
              <ToggleChip
                key={opt.value}
                active={value.operation === opt.value}
                onClick={() =>
                  patch({ operation: value.operation === opt.value ? null : opt.value })
                }
              >
                {opt.label}
              </ToggleChip>
            ))}
          </div>
        </FilterField>

        {/* Capa objetivo — select */}
        <FilterField label="Capa" htmlFor={layerId}>
          <select
            id={layerId}
            value={value.targetLayer ?? ""}
            onChange={(e) =>
              patch({ targetLayer: (e.target.value || null) as AuditTargetLayerT | null })
            }
            className={SELECT_CLASS}
          >
            <option value="">Todas</option>
            {LAYER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </FilterField>

        {/* Modelo de origen — select */}
        <FilterField label="Modelo" htmlFor={modelId}>
          <select
            id={modelId}
            value={value.originModel ?? ""}
            onChange={(e) =>
              patch({ originModel: (e.target.value || null) as AuditOriginModelT | null })
            }
            className={SELECT_CLASS}
          >
            <option value="">Todos</option>
            {MODEL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </FilterField>

        {/* Sensibilidad — tri-estado */}
        <FilterField label="Sensibilidad">
          <div className="flex flex-wrap gap-2">
            <ToggleChip
              active={value.sensitive === true}
              onClick={() => patch({ sensitive: value.sensitive === true ? null : true })}
            >
              Sensibles
            </ToggleChip>
            <ToggleChip
              active={value.sensitive === false}
              onClick={() => patch({ sensitive: value.sensitive === false ? null : false })}
            >
              No sensibles
            </ToggleChip>
          </div>
        </FilterField>
      </div>

      {/* Modo de origen — ModeChip toggles (los 5 tints) */}
      <div className="flex flex-col gap-2">
        <span className="text-caption text-[var(--color-ink-soft)]">Modo de origen</span>
        <div className="flex flex-wrap items-center gap-2">
          {MODES.map((mode) => {
            const active = value.originMode === mode.id;
            return (
              <button
                key={mode.id}
                type="button"
                aria-pressed={active}
                onClick={() => patch({ originMode: active ? null : mode.id })}
                className={cn(
                  "rounded-[var(--radius-pill)] transition-opacity duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
                  "focus-visible:outline-none",
                  active
                    ? "opacity-100 ring-2 ring-[var(--color-selected-ring)]"
                    : "opacity-70 hover:opacity-100",
                )}
              >
                <ModeChip modeId={mode.id} size="sm" />
              </button>
            );
          })}

          {isDirty ? (
            <Button
              variant="ghost"
              onClick={() => onChange({ ...EMPTY_AUDIT_FILTERS })}
              className="ml-2 px-3 py-1.5"
            >
              Limpiar filtros
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
