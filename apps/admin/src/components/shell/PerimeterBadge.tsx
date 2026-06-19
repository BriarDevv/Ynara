"use client";

import { useId, useState } from "react";
import { Diamond } from "@/components/ui/Diamond";
import { cn } from "@/lib/cn";

/**
 * `PerimeterBadge` — la FIRMA de soberanía del panel (blueprint §2.1).
 *
 * Un `Diamond` (el acento de marca) + label, que comunica de un vistazo el
 * estado del perímetro: el contrato de que el token no viaja a host ajeno, el
 * contenido de memoria nunca se descifra y el `record_hash` jamás se expone.
 *
 * Estados:
 *  - `intact`    → azul de marca, diamante latiendo lento (`anim-pulse-soft`).
 *  - `attention` → `--color-error`, sin pulso (algo requiere mirada).
 *  - `verifying` → `ink-soft`, shimmer suave (chequeo en curso).
 *
 * Variantes: `compact` (chip del topbar) y `hero` (banda del Overview, más aire
 * + estado en texto grande). NUNCA gradiente — el diamante es color plano (regla
 * de marca: el gradiente vive sólo en LivingField / YnaraMark / YnaraOrb).
 */
export type PerimeterStatus = "intact" | "attention" | "verifying";

type Props = {
  variant: "compact" | "hero";
  status: PerimeterStatus;
  /** Detalle opcional bajo el label (hero) o en el tooltip (compact). */
  detail?: string;
};

const STATUS_LABEL: Record<PerimeterStatus, string> = {
  intact: "Perímetro intacto",
  attention: "Perímetro · atención",
  verifying: "Verificando perímetro",
};

/** Color del diamante + texto por estado. Tokens, cero hex. */
const STATUS_COLOR: Record<PerimeterStatus, string> = {
  intact: "var(--color-blue-flat)",
  attention: "var(--color-error)",
  verifying: "var(--color-ink-soft)",
};

const TOOLTIP =
  "Soberanía: el token nunca viaja a un host ajeno, el contenido de memoria no se descifra y el hash de integridad no se expone.";

export function PerimeterBadge({ variant, status, detail }: Props) {
  const tooltipId = useId();
  const [open, setOpen] = useState(false);
  const color = STATUS_COLOR[status];
  const label = STATUS_LABEL[status];
  const tooltipText = detail ?? TOOLTIP;

  const diamond = (
    <Diamond
      size={variant === "hero" ? 16 : 11}
      color={color}
      className={
        status === "intact" ? "anim-pulse-soft" : status === "verifying" ? "opacity-70" : undefined
      }
    />
  );

  if (variant === "hero") {
    return (
      <div className="relative flex flex-col gap-2">
        <span className="text-caption text-[var(--color-ink-soft)]">Estado de soberanía</span>
        <span className="flex items-center gap-3">
          {diamond}
          <span className="text-title text-[var(--color-ink-deep)]" style={{ color }}>
            {label}
          </span>
        </span>
        <p className="max-w-[44ch] text-body-sm text-[var(--color-ink-soft)]">{tooltipText}</p>
      </div>
    );
  }

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-describedby={tooltipId}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] px-3 py-1.5"
      >
        {diamond}
        <span className="text-caption" style={{ color }}>
          {label}
        </span>
      </button>
      {/* Tooltip de soberanía. Solo visible en hover/focus; aria-describedby lo liga al chip. */}
      <span
        id={tooltipId}
        role="tooltip"
        className={cn(
          "anim-fade-in pointer-events-none absolute left-1/2 top-full z-[var(--z-topbar)] mt-2 w-64 -translate-x-1/2 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-body-sm text-[var(--color-ink-soft)] shadow-lifted",
          open ? "block" : "hidden",
        )}
      >
        {tooltipText}
      </span>
    </span>
  );
}
