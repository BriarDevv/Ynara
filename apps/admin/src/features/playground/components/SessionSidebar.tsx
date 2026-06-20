"use client";

import { Icon } from "@ynara/ui";
import { type KeyboardEvent, useState } from "react";
import { cn } from "@/lib/cn";
import { relativeTime } from "@/lib/relativeTime";
import type { PlaygroundSession } from "@/stores/playgroundSessions";

type Props = {
  sessions: readonly PlaygroundSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
  className?: string;
};

/**
 * Riel izquierdo del Playground: historial de sesiones (client-side).
 *
 * Lista las conversaciones de prueba guardadas en `usePlaygroundSessions`
 * (localStorage). La activa lleva borde azul de marca. Cada ítem: título
 * (autotitulado por el 1er mensaje), conteo de turnos `tabular-nums` + tiempo
 * relativo, y un botón de borrar al hover. Doble-click en el título → rename
 * inline (Enter confirma, Escape cancela). Botón "Nueva sesión" arriba.
 */
export function SessionSidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onRename,
  className,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const startEdit = (session: PlaygroundSession) => {
    setEditingId(session.id);
    setDraft(session.title);
  };

  const commitEdit = () => {
    if (editingId) onRename(editingId, draft);
    setEditingId(null);
  };

  const onEditKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") commitEdit();
    else if (e.key === "Escape") setEditingId(null);
  };

  return (
    <aside className={cn("flex flex-col gap-3", className)}>
      <button
        type="button"
        onClick={onNew}
        className="flex items-center justify-center gap-2 rounded-[var(--radius-md)] border border-[var(--color-border-strong)] px-4 py-2.5 text-button text-[var(--color-ink)] transition-colors duration-[var(--duration-fast)] hover:border-[var(--color-ink)] hover:bg-[var(--color-bg-soft)]"
      >
        <span aria-hidden className="text-[var(--color-blue-flat)]">
          +
        </span>
        Nueva sesión
      </button>

      <div className="flex items-center justify-between px-1">
        <p className="text-caption text-[var(--color-ink-soft)]">Sesiones</p>
        <span className="text-caption tabular-nums text-[var(--color-ink-soft)]">
          {sessions.length}
        </span>
      </div>

      {sessions.length === 0 ? (
        <p className="px-1 text-body-sm text-[var(--color-ink-soft)]">
          Sin sesiones todavía. Empezá una conversación con el modelo.
        </p>
      ) : (
        <ul className="flex flex-col gap-1.5 overflow-y-auto scrollbar-none">
          {sessions.map((session) => {
            const active = session.id === activeId;
            const turns = session.messages.length;
            return (
              <li key={session.id} className="group relative">
                {editingId === session.id ? (
                  <input
                    // biome-ignore lint/a11y/noAutofocus: rename inline, foco esperado al entrar al modo edición.
                    autoFocus
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={onEditKey}
                    onBlur={commitEdit}
                    aria-label="Renombrar sesión"
                    className="w-full rounded-[var(--radius-md)] border border-[var(--color-blue-flat)] bg-[var(--color-bg)] px-3 py-2 text-body-sm text-[var(--color-ink)] outline-none"
                  />
                ) : (
                  <button
                    type="button"
                    onClick={() => onSelect(session.id)}
                    onDoubleClick={() => startEdit(session)}
                    className={cn(
                      "flex w-full flex-col gap-0.5 rounded-[var(--radius-md)] border px-3 py-2 pr-9 text-left transition-colors duration-[var(--duration-fast)]",
                      active
                        ? "border-[var(--color-blue-flat)] bg-[var(--color-bg-soft)]"
                        : "border-transparent hover:border-[var(--color-border)] hover:bg-[var(--color-bg-soft)]",
                    )}
                  >
                    <span className="truncate text-body-sm text-[var(--color-ink)]">
                      {session.title}
                    </span>
                    <span className="flex items-center gap-2 text-caption text-[var(--color-ink-soft)]">
                      <span className="tabular-nums">{turns}</span>
                      <span aria-hidden>·</span>
                      <span className="tabular-nums">{relativeTime(session.updatedAt)}</span>
                    </span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => onDelete(session.id)}
                  aria-label={`Borrar sesión ${session.title}`}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded-[var(--radius-sm)] p-1 text-[var(--color-ink-muted)] opacity-0 transition-opacity duration-[var(--duration-fast)] hover:text-[var(--color-error)] focus-visible:opacity-100 group-hover:opacity-100"
                >
                  <Icon name="cerrar" size={14} />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}
