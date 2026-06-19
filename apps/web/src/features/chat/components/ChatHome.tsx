"use client";

import { Icon } from "@ynara/ui";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { LivingField } from "@/components/ui/LivingField";
import { ModeSheet } from "@/components/ui/ModeSheet";
import { MODE_BY_ID } from "@/components/ui/modes";
import { useChatStore } from "@/features/chat/store";
import { useActiveMode } from "@/hooks/useActiveMode";
import { SessionsList } from "./SessionsList";

/**
 * Landing de la tab **Chat**: conversaciones recientes (retomar) + arranque de
 * una nueva. La nueva conversación arranca en el **modo activo** de un toque —
 * sin muro de "elegí un modo" (esa fricción se sacó). El modo se cambia con el
 * chip, que abre el `ModeSheet` compartido (fija el modo global). Una sesión =
 * un modo, así que la sesión nace en el modo activo del momento.
 */
export function ChatHome() {
  const router = useRouter();
  const createSession = useChatStore((s) => s.createSession);
  const activeMode = useActiveMode();
  const [sheetOpen, setSheetOpen] = useState(false);
  const mode = MODE_BY_ID[activeMode];

  const startNew = () => {
    const id = createSession(activeMode);
    router.push(`/chat/${id}`);
  };

  return (
    <div className="relative isolate flex min-h-full flex-col">
      {/* Fondo vivo de Hablar (constellation, DESIGN.md §2.2), teñido por el
          modo activo — paridad con la pantalla de conversación, que ya lo
          tenía. El landing era el único de la tab sin fondo (quedaba liso). */}
      <LivingField variant="constellation" modeId={activeMode} />

      <div className="mx-auto flex w-full max-w-[640px] flex-col gap-8 px-6 py-8">
        <header className="flex flex-col gap-2">
          <h1 className="text-display text-[var(--color-ink-deep)]">¿De qué hablamos?</h1>
          <p className="text-body text-[var(--color-ink-soft)]">
            Retomá una conversación o empezá una nueva.
          </p>
        </header>

        <SessionsList />

        <section className="flex flex-col gap-3">
          <h2 className="text-caption text-[var(--color-ink-soft)]">EMPEZAR UNA NUEVA</h2>

          {/* Acción primaria: arranca en el modo activo, sin elegir nada. El fill
            del modo es AA-safe con texto blanco (regla fill-vs-tint). */}
          <button
            type="button"
            onClick={startNew}
            className="flex items-center justify-center gap-2 rounded-[var(--radius-lg)] px-4 py-3.5 text-button font-semibold text-white transition-opacity duration-[var(--duration-fast)] hover:opacity-90"
            style={{ backgroundColor: mode.fillVar }}
          >
            <Icon name="dialogo" size={20} />
            Nueva conversación
          </button>

          {/* Cambiar el modo con el que arranca (abre el picker global). */}
          <button
            type="button"
            onClick={() => setSheetOpen(true)}
            aria-haspopup="dialog"
            aria-label={`Modo ${mode.label}. Cambiar de modo`}
            className="inline-flex items-center justify-center gap-2 self-center rounded-[var(--radius-pill)] px-3 py-1.5 text-body-sm transition-colors duration-[var(--duration-fast)] hover:bg-[var(--color-bg-soft)]"
          >
            <span
              aria-hidden
              className="h-2 w-2 shrink-0 rounded-[var(--radius-pill)]"
              style={{ backgroundColor: mode.tintVar }}
            />
            <span className="text-[var(--color-ink-soft)]">
              Modo · <span className="font-semibold text-[var(--color-ink)]">{mode.label}</span> ·
              cambiar
            </span>
          </button>
        </section>
      </div>

      <ModeSheet open={sheetOpen} onClose={() => setSheetOpen(false)} current={activeMode} />
    </div>
  );
}
