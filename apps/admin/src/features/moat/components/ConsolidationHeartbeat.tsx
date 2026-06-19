"use client";

import type { CSSProperties } from "react";
import { Card } from "@/components/ui/Card";
import { Diamond } from "@/components/ui/Diamond";
import { YnaraOrb } from "@/components/ui/YnaraOrb";
import type { AdminMoatOutT } from "@/features/moat/schemas";
import { cn } from "@/lib/cn";
import { relativeTime } from "@/lib/relativeTime";
import { fmtInt } from "@/lib/time";

/**
 * Mapea el backlog a la duración del latido del orbe (`--orb-beat`): vacío =
 * 4200ms (calmo), cargado (≥40) = 1500ms (acelerado). Misma escala que el orbe
 * del hero, para que las dos firmas de la pantalla respiren al mismo ritmo.
 */
function beatFromBacklog(backlog: number): string {
  const SLOW = 4200;
  const FAST = 1500;
  const FULL_AT = 40;
  const t = Math.max(0, Math.min(1, backlog / FULL_AT));
  return `${Math.round(SLOW - (SLOW - FAST) * t)}ms`;
}

type Props = {
  /** Bloque `consolidation` del contrato: backlog + episodics recientes. */
  consolidation: AdminMoatOutT["consolidation"];
  className?: string;
};

/**
 * `ConsolidationHeartbeat` — el pulso de la consolidación de memoria. A la
 * izquierda un orbe (`YnaraOrb`) cuyo latido se acelera con el backlog pendiente
 * (`--orb-beat` mapeado al tamaño de la cola) + el número de pendientes
 * `text-display tabular-nums`. A la derecha, los episodios consolidados más
 * recientes — **solo metadata** (timestamp + flag de sensible), jamás el
 * contenido descifrado (regla #6).
 *
 * Honestidad de dato: el caption aclara que se muestra metadata, no texto, y los
 * sensibles se marcan con un `Diamond` lleno en vez de revelar nada.
 */
export function ConsolidationHeartbeat({ consolidation, className }: Props) {
  const { backlog, recent_episodic } = consolidation;
  const beat = beatFromBacklog(backlog);
  // El orbe acelera ("Ynara está consolidando") cuando hay cola pendiente.
  const thinking = backlog > 0;

  return (
    <Card className={cn("flex flex-col gap-6 lg:flex-row lg:items-stretch", className)}>
      {/* Pulso de la cola: orbe + número pendiente. */}
      <div
        className="flex shrink-0 flex-col items-center justify-center gap-4 lg:w-64"
        style={{ "--orb-beat": beat } as CSSProperties}
      >
        <YnaraOrb size={72} modeId="memoria" thinking={thinking} glow="ambient" />
        <div className="flex flex-col items-center gap-1 text-center">
          <span className="text-display tabular-nums text-[var(--color-ink-deep)]">
            {fmtInt(backlog)}
          </span>
          <p className="text-caption text-[var(--color-ink-soft)]">episodios por consolidar</p>
        </div>
      </div>

      {/* Episodios recientes (metadata pura). */}
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <header className="flex flex-col gap-1">
          <p className="text-caption text-[var(--color-ink-soft)]">Consolidación</p>
          <h2 className="text-subtitle text-[var(--color-ink-deep)]">Episodios recientes</h2>
          <p className="text-body-sm text-[var(--color-ink-soft)]">
            Solo metadata — Ynara nunca expone el contenido del recuerdo.
          </p>
        </header>

        {recent_episodic.length === 0 ? (
          <p className="text-body-sm text-[var(--color-ink-soft)]">
            Sin episodios recientes en el rango.
          </p>
        ) : (
          <ul className="flex flex-col">
            {recent_episodic.map((ep) => (
              <li
                key={ep.id}
                className="flex items-center justify-between gap-3 border-b border-[var(--color-border)] py-2.5 last:border-b-0"
              >
                <span className="flex items-center gap-2.5">
                  <Diamond
                    size={8}
                    variant={ep.is_sensitive ? "solid" : "outline"}
                    color={ep.is_sensitive ? "var(--color-error)" : "var(--color-ink-faint)"}
                  />
                  <span className="text-body-sm text-[var(--color-ink)]">
                    {ep.is_sensitive ? "Episodio sensible" : "Episodio"}
                  </span>
                </span>
                <time
                  dateTime={ep.occurred_at}
                  className="shrink-0 text-body-sm tabular-nums text-[var(--color-ink-soft)]"
                >
                  {relativeTime(new Date(ep.occurred_at).getTime())}
                </time>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
