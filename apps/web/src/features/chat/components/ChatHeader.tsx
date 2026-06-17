"use client";

import { Icon } from "@ynara/ui";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ModeChip } from "@/components/ui/ModeChip";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
import { ModeSwitcher } from "./ModeSwitcher";

/**
 * Header de la conversación: volver a la home + `ModeChip` del modo de la
 * sesión, que ahora abre el `ModeSwitcher` (cambiar de modo = sesión nueva,
 * chat plan §4.4 / W5).
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
      <button
        type="button"
        onClick={() => setSwitcherOpen(true)}
        aria-haspopup="dialog"
        aria-label={`Modo ${MODE_BY_ID[mode].label}. Cambiar de modo`}
        className="inline-flex items-center gap-1 rounded-[var(--radius-pill)] py-1 pr-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-bg-soft)]"
      >
        <ModeChip modeId={mode} />
        <Icon name="chevron" size={16} />
      </button>
      <ModeSwitcher open={switcherOpen} onClose={() => setSwitcherOpen(false)} currentMode={mode} />
    </header>
  );
}
