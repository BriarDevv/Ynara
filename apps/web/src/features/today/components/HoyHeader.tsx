import type { ModeId } from "@/components/ui/modes";
import { formatHoyDate } from "../format";
import { ModeChip } from "./ModeChip";

type Props = {
  displayName: string;
  activeMode: ModeId;
  /** Referencia temporal (inyectada para evitar drift entre renders). */
  now: Date;
};

/**
 * Header del dashboard Hoy (wireframe 06): fila superior con el chip de modo y
 * el avatar, después el título "Hoy" (display) y la fecha larga en español.
 * Sube fidelidad sobre el wireframe con la tipografía editorial del sistema v2.
 */
export function HoyHeader({ displayName, activeMode, now }: Props) {
  const initial = displayName.trim().charAt(0).toUpperCase();
  return (
    <header className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <ModeChip mode={activeMode} />
        <span
          aria-hidden
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--color-bg-soft)] text-body-sm font-medium text-[var(--color-ink-soft)]"
        >
          {initial}
        </span>
      </div>
      <div className="flex flex-col gap-1">
        <h1 className="text-title text-[var(--color-ink)]">Hoy</h1>
        <p className="text-body text-[var(--color-ink-soft)]">{formatHoyDate(now)}</p>
      </div>
    </header>
  );
}
