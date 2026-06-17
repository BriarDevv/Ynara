"use client";

import { Icon } from "@ynara/ui";
import { useState } from "react";
import { ModeSheet } from "@/components/ui/ModeSheet";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
import { YnaraOrb } from "@/components/ui/YnaraOrb";
import { formatHoyDate, greet } from "../format";

type Props = {
  displayName: string;
  activeMode: ModeId;
  /** Referencia temporal (inyectada para evitar drift entre renders). */
  now: Date;
};

/**
 * Header del dashboard Hoy (wireframe 06 / mockup): fila superior con el chip de
 * modo y el avatar, después la **presencia de Ynara** — el orbe (teñido por el
 * modo activo) junto al saludo personalizado ("Buen día, Mateo.") y la fecha
 * larga. El saludo reemplaza el título "Hoy" plano: es el hero de la pantalla.
 *
 * El chip de modo es **interactivo** (paridad con el mockup): abre el `ModeSheet`
 * compartido para cambiar el modo activo desde acá, sin pasar por el chat.
 */
export function HoyHeader({ displayName, activeMode, now }: Props) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const name = displayName.trim();
  const initial = name.charAt(0).toUpperCase() || "Y";
  const saludo = name ? `${greet(now)}, ${name}.` : `${greet(now)}.`;
  const mode = MODE_BY_ID[activeMode];

  return (
    <header className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => setSheetOpen(true)}
          aria-haspopup="dialog"
          aria-label={`Modo ${mode.label}. Cambiar de modo`}
          className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)] py-1.5 pr-2 pl-3 text-body-sm transition-colors duration-[var(--duration-fast)] hover:bg-[var(--color-border)]"
        >
          <span
            aria-hidden
            className="h-2 w-2 shrink-0 rounded-[var(--radius-pill)]"
            style={{ backgroundColor: mode.tintVar }}
          />
          <span className="text-[var(--color-ink-soft)]">
            Modo · <span className="font-semibold text-[var(--color-ink)]">{mode.label}</span>
          </span>
          <Icon name="chevron" size={16} className="text-[var(--color-ink-soft)]" />
        </button>
        <span
          aria-hidden
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--color-bg-soft)] text-body-sm font-medium text-[var(--color-ink-soft)]"
        >
          {initial}
        </span>
      </div>
      <div className="flex items-start gap-4">
        <YnaraOrb size={56} modeId={activeMode} className="mt-1" />
        <div className="flex flex-col gap-1">
          <h1 className="text-title text-[var(--color-ink-deep)]">{saludo}</h1>
          <p className="text-body text-[var(--color-ink-soft)]">{formatHoyDate(now)}</p>
        </div>
      </div>

      <ModeSheet open={sheetOpen} onClose={() => setSheetOpen(false)} current={activeMode} />
    </header>
  );
}
