import { Icon } from "@ynara/ui";
import Link from "next/link";
import type { CSSProperties } from "react";
import { Diamond } from "@/components/ui/Diamond";
import { cn } from "@/lib/cn";
import { LAYER_BY_ID } from "../layers";
import { formatEntryDate, type TimelineEntry } from "../timeline";

type Props = {
  entry: TimelineEntry;
  /** Referencia temporal para la meta relativa (inyectada para evitar drift). */
  now: Date;
  /** Índice dentro de la lista, para el stagger de entrada (§8.2). */
  index: number;
};

/**
 * Una fila del timeline de memoria: badge de capa + el recuerdo + su fecha
 * relativa. Es un link al detalle (`/memoria/{ref}?capa={layer}`): la capa va
 * por query porque la ruta `[id]` es de un solo segmento y el detalle del
 * backend necesita `{layer}/{ref}`.
 */
export function TimelineEntryRow({ entry, now, index }: Props) {
  const layer = LAYER_BY_ID[entry.layer];
  return (
    <li
      className="anim-stagger-up"
      style={{ "--stagger-index": Math.min(index, 5) } as CSSProperties}
    >
      <Link
        href={`/memoria/${encodeURIComponent(entry.ref)}?capa=${entry.layer}`}
        className={cn(
          "group flex min-h-[44px] items-center gap-3 px-2 py-3.5",
          "rounded-[var(--radius-md)] transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
          "hover:bg-[var(--color-bg-soft)]",
        )}
      >
        {/* Marcador de capa: diamante teñido por la capa, como el mockup tiñe
            cada fila por su tag. Calmo, sin caja. */}
        <Diamond size={11} color={layer.color} className="mt-[7px] self-start" />
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="text-caption text-[var(--color-ink-soft)]">{layer.label}</span>
          <span className="line-clamp-2 text-body text-[var(--color-ink)]">{entry.title}</span>
        </span>
        <span className="mt-0.5 shrink-0 self-start text-body-sm tabular-nums text-[var(--color-ink-soft)]">
          {formatEntryDate(entry.date, now)}
        </span>
        <span
          aria-hidden
          className="mt-0.5 shrink-0 self-start text-[var(--color-ink-faint)] transition-colors duration-[var(--duration-fast)] group-hover:text-[var(--color-ink-muted)]"
        >
          <Icon name="chevron" size={18} className="-rotate-90" />
        </span>
      </Link>
    </li>
  );
}
