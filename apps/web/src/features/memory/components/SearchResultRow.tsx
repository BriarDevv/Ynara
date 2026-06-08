import type { MemorySearchHit } from "@ynara/shared-schemas";
import { Icon } from "@ynara/ui";
import Link from "next/link";
import type { CSSProperties } from "react";
import { cn } from "@/lib/cn";
import { LAYER_BY_ID } from "../layers";
import { formatEntryDate } from "../timeline";

type Props = {
  hit: MemorySearchHit;
  now: Date;
  index: number;
};

/**
 * Una fila de resultado de búsqueda: badge de capa + el fragmento que matcheó +
 * su fecha. Linkea al detalle igual que el timeline. Misma forma visual que
 * `TimelineEntryRow` pero sobre un `MemorySearchHit` (snippet + fecha opcional).
 */
export function SearchResultRow({ hit, now, index }: Props) {
  const layer = LAYER_BY_ID[hit.layer];
  return (
    <li
      className="anim-stagger-up"
      style={{ "--stagger-index": Math.min(index, 5) } as CSSProperties}
    >
      <Link
        href={`/memoria/${encodeURIComponent(hit.ref)}?capa=${hit.layer}`}
        className={cn(
          "group flex items-start gap-4 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)] p-4",
          "transition-[transform,box-shadow,border-color] duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
          "hover:border-[var(--color-border-strong)] hover:shadow-soft",
        )}
      >
        <span
          aria-hidden
          className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--color-bg-soft)] text-[var(--color-memory)]"
        >
          <Icon name={layer.icon} size={20} />
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="text-caption text-[var(--color-ink-soft)]">{layer.label}</span>
          <span className="line-clamp-2 text-body text-[var(--color-ink)]">{hit.snippet}</span>
          {hit.occurred_at ? (
            <span className="text-body-sm tabular-nums text-[var(--color-ink-soft)]">
              {formatEntryDate(hit.occurred_at, now)}
            </span>
          ) : null}
        </span>
        <span
          aria-hidden
          className="mt-1 shrink-0 text-[var(--color-ink-faint)] transition-colors duration-[var(--duration-fast)] group-hover:text-[var(--color-ink-muted)]"
        >
          <Icon name="chevron" size={18} className="-rotate-90" />
        </span>
      </Link>
    </li>
  );
}
