import type { CSSProperties } from "react";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
import { cn } from "@/lib/cn";

/**
 * `YnaraOrb` — la presencia viva de Ynara (DESIGN.md §2, §8): el atributo
 * *Presencia* hecho componente. Dos anillos + diamante central con un latido
 * lento y único (el core, 4.2s). Con `thinking` el latido se acelera (1.5s) —
 * "Ynara está pensando".
 *
 * Port de `YnaraOrb` del prototipo (§15), con el acento resuelto por tokens:
 * el color sale del tint del modo (`--mode-*`) vía `color-mix`, así el orbe
 * se tiñe con el modo activo y sobrevive a cambios de paleta sin tocar JS.
 *
 * **Glow contenido (no derramado).** El glow ambiental es un gradiente radial
 * que blendea contra `--color-bg` —no contra `transparent`— y se derrama poco
 * (`inset` chico), así se comporta como una fuente de luz embebida en la
 * superficie en vez de un halo saturado "pegado encima". El nivel se regula
 * con `glow`: `quiet` (default, header/typing), `ambient` (showcases como el
 * Paywall) o `none`. §3.4 lista los portadores legítimos de gradiente (el
 * fondo vivo, el logo y este glow) y el guard anti-gradiente allowlistea este
 * archivo. Decorativo puro: `aria-hidden` — el estado "pensando" lo anuncia el
 * contexto (p. ej. el indicador del chat), no el orbe.
 */

type GlowLevel = "ambient" | "quiet" | "none";

/** Receta del glow por nivel: `mix` = % de acento sobre `--color-bg`,
 *  `inset` = cuánto se derrama (fracción del tamaño), `stop` = corte radial. */
const GLOW: Record<Exclude<GlowLevel, "none">, { mix: number; inset: number; stop: number }> = {
  ambient: { mix: 34, inset: 0.2, stop: 70 },
  quiet: { mix: 20, inset: 0.1, stop: 62 },
};

type Props = {
  /** Diámetro en px. */
  size?: number;
  /** Modo que tiñe el orbe. Default: el azul de marca. */
  modeId?: ModeId | null;
  /** Latido acelerado: Ynara procesando. */
  thinking?: boolean;
  /** Intensidad del glow ambiental. Default: `quiet`. */
  glow?: GlowLevel;
  className?: string;
};

export function YnaraOrb({
  size = 44,
  modeId = null,
  thinking = false,
  glow = "quiet",
  className,
}: Props) {
  const accent = modeId ? MODE_BY_ID[modeId].tintVar : "var(--color-azul)";
  const mix = (pct: number) => `color-mix(in srgb, ${accent} ${pct}%, transparent)`;
  const g = glow === "none" ? null : GLOW[glow];

  return (
    <div
      aria-hidden
      className={cn("relative shrink-0", className)}
      // `--orb-beat` controla la duración del latido del core (el hijo la
      // hereda). Va por var y no por un selector descendente para no ganarle
      // en specificity a la cascada global de reduced-motion.
      style={
        { width: size, height: size, "--orb-beat": thinking ? "1500ms" : "4200ms" } as CSSProperties
      }
    >
      {/* Glow ambiental contenido: blendea contra el fondo, se derrama poco. */}
      {g ? (
        <div
          className="absolute rounded-[var(--radius-pill)]"
          style={{
            inset: -size * g.inset,
            background: `radial-gradient(circle, color-mix(in srgb, ${accent} ${g.mix}%, var(--color-bg)) 0%, transparent ${g.stop}%)`,
          }}
        />
      ) : null}
      {/* Anillo exterior (estático) */}
      <div
        className="absolute inset-0 rounded-[var(--radius-pill)]"
        style={{ border: `1.5px solid ${mix(50)}` }}
      />
      {/* Anillo medio (estático) */}
      <div
        className="absolute rounded-[var(--radius-pill)]"
        style={{ inset: size * 0.16, border: `1px solid ${mix(50)}` }}
      />
      {/* Diamante central — el único elemento que late. */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div
          className="anim-orb-core rotate-45"
          style={{
            width: size * 0.3,
            height: size * 0.3,
            borderRadius: size * 0.06,
            backgroundColor: mix(90),
            boxShadow: `0 0 ${size * 0.28}px ${mix(40)}`,
          }}
        />
      </div>
    </div>
  );
}
