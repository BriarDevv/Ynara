import type { CSSProperties } from "react";
import { cn } from "@/lib/cn";
import type { Task } from "../api";
import { formatTaskMeta } from "../format";

type Props = {
  task: Task;
  onToggle: (task: Task) => void;
  /** Índice en la lista, para el stagger de entrada (§8.2). */
  index: number;
};

/**
 * Una prioridad del día (wireframe 06): el check a la izquierda (toggle
 * pending↔done) + el título + la meta "14:00 · 45 min" / "09:15 · completada".
 * Hecha → título atenuado. El check es un `checkbox` accesible; el toggle es
 * optimista (lo maneja el hook en la sección).
 */
export function PriorityRow({ task, onToggle, index }: Props) {
  const done = task.status === "done";
  const meta = formatTaskMeta(task);
  return (
    <li
      className="anim-stagger-up flex items-start gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)] p-4"
      style={{ "--stagger-index": Math.min(index, 5) } as CSSProperties}
    >
      {/* biome-ignore lint/a11y/useSemanticElements: <input type="checkbox"> no acepta el relleno custom (anillo → punto) ni el spacing/transición del check. Conserva a11y vía role="checkbox" + aria-checked + aria-label + foco nativo del <button>. */}
      <button
        type="button"
        role="checkbox"
        aria-checked={done}
        aria-label={
          done ? `Marcar "${task.title}" como pendiente` : `Marcar "${task.title}" como hecha`
        }
        onClick={() => onToggle(task)}
        className={cn(
          "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
          done
            ? "border-[var(--color-ink)] bg-[var(--color-ink)]"
            : "border-[var(--color-border-strong)] bg-transparent hover:border-[var(--color-ink)]",
        )}
      >
        {done ? <span aria-hidden className="h-2 w-2 rounded-full bg-[var(--color-bg)]" /> : null}
      </button>
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span
          className={cn(
            "text-body",
            done ? "text-[var(--color-ink-soft)]" : "text-[var(--color-ink)]",
          )}
        >
          {task.title}
        </span>
        {meta ? (
          <span className="text-body-sm tabular-nums text-[var(--color-ink-muted)]">{meta}</span>
        ) : null}
      </span>
    </li>
  );
}
