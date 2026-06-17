"use client";

import { Icon } from "@ynara/ui";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ModeChip } from "@/components/ui/ModeChip";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
import { YnaraOrb } from "@/components/ui/YnaraOrb";
import { ModeSwitcher } from "./ModeSwitcher";

/**
 * Header de la conversación (mockup): volver + **presencia de Ynara** (orbe
 * teñido por el modo + "Ynara") y, a la derecha, el `ModeChip` que abre el
 * `ModeSwitcher` (cambiar de modo = sesión nueva, chat plan §4.4 / W5).
 */
export function ChatHeader({ mode }: { mode: ModeId }) {
  const router = useRouter();
  const [switcherOpen, setSwitcherOpen] = useState(false);

  return (
    <header className="flex items-center gap-3 border-b border-[var(--color-border)] px-4 py-3">
      <button
        type="button"
        onClick={() => router.push("/hoy")}
        aria-label="Volver al inicio"
        className="flex h-11 w-11 items-center justify-center rounded-[var(--radius-pill)] text-[var(--color-ink-soft)] hover:bg-[var(--color-bg-soft)] hover:text-[var(--color-ink)]"
      >
        <Icon name="atras" size={20} />
      </button>
      <YnaraOrb size={34} modeId={mode} />
      <span
        className="text-body font-semibold text-[var(--color-ink)]"
        style={{ fontFamily: "var(--font-display), 'Space Grotesk', system-ui, sans-serif" }}
      >
        Ynara
      </span>
      <button
        type="button"
        onClick={() => setSwitcherOpen(true)}
        aria-haspopup="dialog"
        aria-label={`Modo ${MODE_BY_ID[mode].label}. Cambiar de modo`}
        className="ml-auto inline-flex items-center gap-1 rounded-[var(--radius-pill)] py-1 pr-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-bg-soft)]"
      >
        <ModeChip modeId={mode} />
        <Icon name="chevron" size={16} />
      </button>
      <ModeSwitcher open={switcherOpen} onClose={() => setSwitcherOpen(false)} currentMode={mode} />
    </header>
  );
}
