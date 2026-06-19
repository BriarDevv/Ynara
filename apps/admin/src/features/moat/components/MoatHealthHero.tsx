"use client";

import type { CSSProperties } from "react";
import { Diamond } from "@/components/ui/Diamond";
import { LivingField } from "@/components/ui/LivingField";
import { cn } from "@/lib/cn";
import { fmtInt } from "@/lib/time";

/**
 * Mapea el tamaño del backlog de consolidación a la duración del latido del
 * orbe central (`--orb-beat`): backlog calmo (0) → 4200ms (respiración lenta);
 * backlog cargado (≥40) → 1500ms (acelerado, "Ynara está consolidando"). Es la
 * misma escala que usa `YnaraOrb.thinking` (4200↔1500), acá interpolada de forma
 * continua según la presión real de la cola.
 */
function beatFromBacklog(backlog: number): string {
  const SLOW = 4200;
  const FAST = 1500;
  const FULL_AT = 40; // backlog ≥ 40 = latido más rápido
  const t = Math.max(0, Math.min(1, backlog / FULL_AT));
  return `${Math.round(SLOW - (SLOW - FAST) * t)}ms`;
}

/** Color y etiqueta por capa para los anillos (mismo código que el skyline). */
const RING_META = [
  { key: "semantic" as const, label: "Semántica", colorVar: "var(--layer-semantic)" },
  { key: "episodic" as const, label: "Episódica", colorVar: "var(--layer-episodic)" },
  { key: "procedural" as const, label: "Procedural", colorVar: "var(--layer-procedural)" },
];

type Props = {
  /** Counts por capa. La suma es el total consolidado del centro. */
  counts: { semantic: number; episodic: number; procedural: number };
  /** Backlog de consolidación pendiente — modula el latido del orbe. */
  backlog: number;
  className?: string;
};

/**
 * `MoatHealthHero` — pieza memorable de la pantalla insignia: el "latido de la
 * memoria". Reutiliza `LivingField variant="network" modeId="memoria"` como
 * campo de nodos enlazados (la red viva de la memoria) detrás de un centro con
 * el **total consolidado** `text-display tabular-nums`. El orbe del centro late
 * a un ritmo mapeado al backlog (`--orb-beat`): cuanto más hay por consolidar,
 * más rápido respira. Es la única animación ambiental continua de la pantalla.
 *
 * Honestidad de dato: el centro rotula que el total es la suma de las 3 capas.
 * Color y atmósfera 100% por token; el gradiente vive solo dentro de
 * `LivingField` (portador allowlisteado del gradient-guard), nunca acá.
 */
export function MoatHealthHero({ counts, backlog, className }: Props) {
  const total = counts.semantic + counts.episodic + counts.procedural;
  const beat = beatFromBacklog(backlog);

  return (
    <section
      className={cn(
        "relative isolate flex min-h-72 flex-col items-center justify-center gap-6 overflow-hidden rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-[var(--color-bg)] px-6 py-12 text-center",
        className,
      )}
    >
      {/* Campo vivo como red de nodos: la memoria como tejido conectado. */}
      <LivingField variant="network" modeId="memoria" density="media" />

      {/* Núcleo: orbe latiendo (CSS, anim-orb-core) + total consolidado. */}
      <div className="relative flex flex-col items-center gap-4">
        <div
          aria-hidden
          className="relative grid h-24 w-24 place-items-center"
          style={{ "--orb-beat": beat } as CSSProperties}
        >
          {/* Anillos concéntricos (externo→interno = semántica→procedural). */}
          {RING_META.map((ring, i) => (
            <span
              key={ring.key}
              className="absolute rounded-[var(--radius-pill)]"
              style={{
                inset: i * 14,
                border: `1.5px solid color-mix(in srgb, ${ring.colorVar} 55%, transparent)`,
              }}
            />
          ))}
          {/* Diamante central que late con --orb-beat (mapeado al backlog). */}
          <span
            className="anim-orb-core rotate-45 rounded-[var(--radius-sm)] bg-[var(--color-lavanda)]"
            style={{
              width: 22,
              height: 22,
              boxShadow: "0 0 18px color-mix(in srgb, var(--color-lavanda) 45%, transparent)",
            }}
          />
        </div>

        <div className="flex flex-col items-center gap-1">
          <span className="text-display tabular-nums text-[var(--color-ink-deep)]">
            {fmtInt(total)}
          </span>
          <p className="text-caption text-[var(--color-ink-soft)]">
            memorias consolidadas — suma de las 3 capas
          </p>
        </div>
      </div>

      {/* Leyenda de anillos: documenta el código de color de capa. */}
      <ul className="relative flex flex-wrap items-center justify-center gap-x-5 gap-y-1.5">
        {RING_META.map((ring) => (
          <li key={ring.key} className="flex items-center gap-2">
            <Diamond size={9} color={ring.colorVar} />
            <span className="text-body-sm text-[var(--color-ink-soft)]">{ring.label}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
