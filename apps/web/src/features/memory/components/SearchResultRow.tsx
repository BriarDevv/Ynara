import type { MemorySearchHit } from "@ynara/shared-schemas";
import { Icon } from "@ynara/ui";
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { Diamond } from "@/components/ui/Diamond";
import { cn } from "@/lib/cn";
import { LAYER_BY_ID } from "../layers";
import { formatEntryDate } from "../timeline";

type Props = {
  hit: MemorySearchHit;
  now: Date;
  index: number;
  /** Término buscado, para resaltar las coincidencias en el snippet. */
  query?: string;
};

/**
 * Resalta las coincidencias de `query` dentro de `text` envolviéndolas en
 * `<mark>`. Trabaja con nodos de texto (split por regex escapado), nunca con
 * innerHTML, así que es seguro contra XSS. Case-insensitive; conserva el
 * casing original del texto.
 */
function highlight(text: string, query: string | undefined): ReactNode {
  const q = query?.trim();
  if (!q) return text;
  const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = text.split(new RegExp(`(${escaped})`, "gi"));
  return parts.map((part, i) =>
    part.toLowerCase() === q.toLowerCase() ? (
      <mark
        // biome-ignore lint/suspicious/noArrayIndexKey: el split es estable para un mismo (text, query)
        key={`${i}-${part}`}
        className="rounded-[3px] px-0.5 text-[var(--color-ink)]"
        style={{ backgroundColor: "color-mix(in srgb, var(--color-memory) 28%, transparent)" }}
      >
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

/**
 * Una fila de resultado de búsqueda: badge de capa + el fragmento que matcheó +
 * su fecha. Linkea al detalle igual que el timeline. Misma forma visual que
 * `TimelineEntryRow` pero sobre un `MemorySearchHit` (snippet + fecha opcional).
 */
export function SearchResultRow({ hit, now, index, query }: Props) {
  const layer = LAYER_BY_ID[hit.layer];
  return (
    <li
      className="anim-stagger-up"
      style={{ "--stagger-index": Math.min(index, 5) } as CSSProperties}
    >
      <Link
        href={`/memoria/${encodeURIComponent(hit.ref)}?capa=${hit.layer}`}
        className={cn(
          "group flex min-h-[44px] items-center gap-3 px-2 py-3.5",
          "rounded-[var(--radius-md)] transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
          "hover:bg-[var(--color-bg-soft)]",
        )}
      >
        {/* Marcador de capa: diamante teñido por la capa (paridad con el
            timeline y el mockup). */}
        <Diamond size={11} color={layer.color} className="mt-[7px] self-start" />
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="text-caption text-[var(--color-ink-soft)]">{layer.label}</span>
          <span className="line-clamp-2 text-body text-[var(--color-ink)]">
            {highlight(hit.snippet, query)}
          </span>
        </span>
        {hit.occurred_at ? (
          <span className="mt-0.5 shrink-0 self-start text-body-sm tabular-nums text-[var(--color-ink-soft)]">
            {formatEntryDate(hit.occurred_at, now)}
          </span>
        ) : null}
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
