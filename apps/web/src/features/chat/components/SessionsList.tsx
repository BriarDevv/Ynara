"use client";

import { useRouter } from "next/navigation";
import { ModeChip } from "@/components/ui/ModeChip";
import { useChatStore } from "@/features/chat/store";
import { relativeTime } from "@/lib/relativeTime";

/**
 * Conversaciones recientes (build-plan Fase D / chat plan W5): las sesiones del
 * chat store ordenadas por `updatedAt`, con `ModeChip` + preview del último
 * mensaje + tiempo relativo. Click → retoma `/chat/[sessionId]`. Devuelve null
 * si no hay sesiones (la landing muestra solo "empezar una nueva"). Espeja el
 * `SessionsList` de mobile con primitives web.
 */
export function SessionsList() {
  const router = useRouter();
  const sessions = useChatStore((s) => s.sessions);
  const messages = useChatStore((s) => s.messages);

  const ordered = Object.values(sessions).sort((a, b) => b.updatedAt - a.updatedAt);
  if (ordered.length === 0) return null;

  const preview = (sessionId: string): string => {
    const list = messages[sessionId] ?? [];
    for (let i = list.length - 1; i >= 0; i--) {
      const text = list[i]?.text.trim();
      if (text) return text;
    }
    return "Conversación vacía";
  };

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-caption text-[var(--color-ink-soft)]">CONVERSACIONES RECIENTES</h2>
      <ul className="flex flex-col gap-2">
        {ordered.map((session) => (
          <li key={session.id}>
            <button
              type="button"
              onClick={() => router.push(`/chat/${session.id}`)}
              className="flex w-full flex-col gap-1.5 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)] p-4 text-left transition-colors hover:bg-[var(--color-bg-soft)]"
            >
              <span className="flex items-center justify-between gap-2">
                <ModeChip modeId={session.mode} />
                <span className="text-caption text-[var(--color-ink-faint)]">
                  {relativeTime(session.updatedAt)}
                </span>
              </span>
              <span className="truncate text-body-sm text-[var(--color-ink-soft)]">
                {preview(session.id)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
