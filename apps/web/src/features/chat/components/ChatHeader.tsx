"use client";

import { Icon } from "@ynara/ui";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ModeChip } from "@/components/ui/ModeChip";
import { ModeSheet } from "@/components/ui/ModeSheet";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
import { YnaraOrb } from "@/components/ui/YnaraOrb";
import { useChatStore } from "../store";

/**
 * Header de la conversación (mockup): volver + **presencia de Ynara** (orbe
 * teñido por el modo + "Ynara") y, a la derecha, el `ModeChip` que abre el
 * `ModeSheet` compartido. Elegir un modo fija el modo activo global; como una
 * sesión = un modo, si el modo elegido difiere del de esta conversación se
 * arranca una conversación nueva en él (la actual queda guardada).
 *
 * `thinking` hace latir el orbe más rápido mientras Ynara responde (presencia
 * como estado, no como adorno): el orbe refleja que está trabajando.
 */
export function ChatHeader({ mode, thinking = false }: { mode: ModeId; thinking?: boolean }) {
  const router = useRouter();
  const createSession = useChatStore((s) => s.createSession);
  const [switcherOpen, setSwitcherOpen] = useState(false);

  const onAfterPick = (next: ModeId) => {
    if (next === mode) return;
    const id = createSession(next);
    router.push(`/chat/${id}`);
  };

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
      <YnaraOrb size={34} modeId={mode} thinking={thinking} />
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
      <ModeSheet
        open={switcherOpen}
        onClose={() => setSwitcherOpen(false)}
        current={mode}
        onAfterPick={onAfterPick}
        note="Cambiar de modo arranca una conversación nueva. Esta queda guardada."
      />
    </header>
  );
}
