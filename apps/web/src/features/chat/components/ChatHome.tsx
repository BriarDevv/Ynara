"use client";

import { useRouter } from "next/navigation";
import { MODES, type ModeId } from "@/components/ui/modes";
import { useChatStore } from "@/features/chat/store";
import { useUserStore } from "@/stores/user";
import { SessionsList } from "./SessionsList";

/**
 * Landing de la tab **Chat** (build-plan Fase D / chat plan W5): conversaciones
 * recientes (retomar) + "empezar una nueva" eligiendo modo (los elegidos en el
 * onboarding aparecen primero). Elegir un modo crea la sesión (una sesión = un
 * modo) y navega a la conversación. Espeja el `ChatHome` de mobile con
 * primitives web.
 */
export function ChatHome() {
  const router = useRouter();
  const createSession = useChatStore((s) => s.createSession);
  const interestedModes = useUserStore((s) => s.interestedModes);

  // Estable: los modos de interés del onboarding primero, sin romper el orden
  // canónico dentro de cada grupo (sort estable en V8).
  const ordered = [...MODES].sort(
    (a, b) => Number(interestedModes.includes(b.id)) - Number(interestedModes.includes(a.id)),
  );

  const start = (mode: ModeId) => {
    const id = createSession(mode);
    router.push(`/chat/${id}`);
  };

  return (
    <div className="mx-auto flex w-full max-w-[640px] flex-col gap-8 px-6 py-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-title text-[var(--color-ink-deep)]">¿De qué hablamos?</h1>
        <p className="text-body text-[var(--color-ink-soft)]">
          Retomá una conversación o empezá una nueva.
        </p>
      </header>

      <SessionsList />

      <section className="flex flex-col gap-3">
        <h2 className="text-caption text-[var(--color-ink-soft)]">EMPEZAR UNA NUEVA</h2>
        <ul className="flex flex-col gap-3">
          {ordered.map((mode) => (
            <li key={mode.id}>
              <button
                type="button"
                onClick={() => start(mode.id)}
                className="flex w-full items-center gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)] p-4 text-left transition-colors hover:bg-[var(--color-bg-soft)]"
              >
                <span
                  aria-hidden
                  className="h-3 w-3 shrink-0 rounded-[var(--radius-pill)]"
                  style={{ backgroundColor: mode.tintVar }}
                />
                <span className="flex flex-1 flex-col">
                  <span className="text-body font-semibold text-[var(--color-ink)]">
                    {mode.label}
                  </span>
                  <span className="text-body-sm text-[var(--color-ink-soft)]">{mode.blurb}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
