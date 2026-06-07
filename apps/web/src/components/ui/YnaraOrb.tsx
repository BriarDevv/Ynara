import type { CSSProperties } from "react";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
import { cn } from "@/lib/cn";

/**
 * `YnaraOrb` — la presencia viva de Ynara (DESIGN.md §2, §8): el atributo
 * *Presencia* hecho componente. Glow ambiental + dos anillos + diamante
 * central, latiendo en un ciclo lento (4.2s). Con `thinking`, el latido se
 * acelera (1.5s) — "Ynara está pensando".
 *
 * Port de `YnaraOrb` del prototipo (§15), con el acento resuelto por tokens:
 * el color sale del tint del modo (`--mode-*`) vía `color-mix`, así el orbe
 * se tiñe con el modo activo y sobrevive a cambios de paleta sin tocar JS.
 *
 * El glow usa un gradiente radial **ambiental** (como el canvas, §3.4 lo
 * permite para atmósfera de marca; lo prohibido es el gradiente como fill
 * de UI). Decorativo puro: `aria-hidden` — el estado "pensando" lo anuncia
 * el contexto (p. ej. el indicador del chat), no el orbe.
 */

type Props = {
  /** Diámetro en px. */
  size?: number;
  /** Modo que tiñe el orbe. Default: el azul de marca. */
  modeId?: ModeId | null;
  /** Latido acelerado: Ynara procesando. */
  thinking?: boolean;
  className?: string;
};

export function YnaraOrb({ size = 44, modeId = null, thinking = false, className }: Props) {
  const accent = modeId ? MODE_BY_ID[modeId].tintVar : "var(--color-azul)";
  const mix = (pct: number) => `color-mix(in srgb, ${accent} ${pct}%, transparent)`;

  return (
    <div
      aria-hidden
      className={cn("relative shrink-0", className)}
      // `--orb-beat` controla la duración de las tres animaciones (los hijos
      // la heredan). Va por var y no por un selector descendente para no
      // ganarle en specificity a la cascada global de reduced-motion.
      style={
        { width: size, height: size, "--orb-beat": thinking ? "1500ms" : "4200ms" } as CSSProperties
      }
    >
      {/* Glow ambiental */}
      <div
        className="anim-orb-pulse absolute rounded-[var(--radius-pill)]"
        style={{
          inset: -size * 0.28,
          background: `radial-gradient(circle, ${mix(45)} 0%, transparent 70%)`,
        }}
      />
      {/* Anillo exterior */}
      <div
        className="anim-orb-ring absolute inset-0 rounded-[var(--radius-pill)]"
        style={{ border: `1.5px solid ${mix(50)}` }}
      />
      {/* Anillo medio */}
      <div
        className="absolute rounded-[var(--radius-pill)]"
        style={{ inset: size * 0.16, border: `1px solid ${mix(50)}` }}
      />
      {/* Diamante central */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div
          className="anim-orb-core rotate-45"
          style={{
            width: size * 0.3,
            height: size * 0.3,
            borderRadius: size * 0.06,
            backgroundColor: mix(90),
            boxShadow: `0 0 ${size * 0.3}px ${mix(70)}`,
          }}
        />
      </div>
    </div>
  );
}
