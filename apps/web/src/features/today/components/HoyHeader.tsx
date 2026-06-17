import { ModeChip } from "@/components/ui/ModeChip";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
import { YnaraOrb } from "@/components/ui/YnaraOrb";
import { formatHoyDate, greet } from "../format";

type Props = {
  displayName: string;
  activeMode: ModeId;
  /** Referencia temporal (inyectada para evitar drift entre renders). */
  now: Date;
};

/**
 * Header del dashboard Hoy (wireframe 06 / mockup): fila superior con el chip de
 * modo y el avatar, después la **presencia de Ynara** — el orbe (teñido por el
 * modo activo) junto al saludo personalizado ("Buen día, Mateo.") y la fecha
 * larga. El saludo reemplaza el título "Hoy" plano: es el hero de la pantalla.
 */
export function HoyHeader({ displayName, activeMode, now }: Props) {
  const name = displayName.trim();
  const initial = name.charAt(0).toUpperCase() || "Y";
  const saludo = name ? `${greet(now)}, ${name}.` : `${greet(now)}.`;

  return (
    <header className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <ModeChip
          modeId={activeMode}
          variant="soft"
          label={`Modo: ${MODE_BY_ID[activeMode].label}`}
        />
        <span
          aria-hidden
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--color-bg-soft)] text-body-sm font-medium text-[var(--color-ink-soft)]"
        >
          {initial}
        </span>
      </div>
      <div className="flex items-start gap-4">
        <YnaraOrb size={56} modeId={activeMode} className="mt-1" />
        <div className="flex flex-col gap-1">
          <h1 className="text-title text-[var(--color-ink-deep)]">{saludo}</h1>
          <p className="text-body text-[var(--color-ink-soft)]">{formatHoyDate(now)}</p>
        </div>
      </div>
    </header>
  );
}
