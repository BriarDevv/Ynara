"use client";

import { useRouter } from "next/navigation";
import { ModeChip } from "@/components/ui/ModeChip";
import type { ModeId } from "@/components/ui/modes";

/**
 * Header de la conversación: volver a la home + `ModeChip` del modo de la
 * sesión. El `ModeSwitcher` (cambiar de modo = nueva sesión) llega en W5.
 */
export function ChatHeader({ mode }: { mode: ModeId }) {
  const router = useRouter();

  return (
    <header className="flex items-center gap-3 border-b border-[var(--color-border)] px-4 py-3">
      <button
        type="button"
        onClick={() => router.push("/hoy")}
        aria-label="Volver al inicio"
        className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-pill)] text-[var(--color-ink-soft)] hover:bg-[var(--color-bg-soft)] hover:text-[var(--color-ink)]"
      >
        ←
      </button>
      <ModeChip modeId={mode} />
    </header>
  );
}
