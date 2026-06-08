import type { MemoryItemOut, MemoryLayer } from "@ynara/shared-schemas";
import { Icon } from "@ynara/ui";
import Link from "next/link";
import { LivingField } from "@/components/ui/LivingField";
import { useActiveMode } from "@/hooks/useActiveMode";
import { presentDetail } from "../detail-presenter";
import { LAYER_BY_ID } from "../layers";
import { formatFullDate, type TimelineEntry } from "../timeline";
import { TimelineEntryRow } from "./TimelineEntryRow";

type Props = {
  layer: MemoryLayer;
  item: MemoryItemOut;
  related: TimelineEntry[];
  relatedPending: boolean;
  now: Date;
  /** Slot para las acciones (editar/borrar). Vacío en la vista de solo lectura. */
  actions?: React.ReactNode;
};

/**
 * Detalle de un recuerdo (wireframe 20 / build-plan C2): back bar, capa, el
 * recuerdo como quote editorial, contexto, meta y relacionados. Sube fidelidad
 * con el design system v2 (tipografía display para el quote, tokens, set de
 * íconos propio). Las acciones se inyectan por slot (C2b).
 */
export function MemoryDetailView({ layer, item, related, relatedPending, now, actions }: Props) {
  const layerInfo = LAYER_BY_ID[layer];
  const p = presentDetail(layer, item);
  const activeMode = useActiveMode();

  return (
    <div className="relative isolate flex min-h-full flex-col">
      {/* Fondo vivo del detalle (network: misma textura que el timeline de
          Memoria del que es continuación — DESIGN.md §2.2), teñido por el modo
          activo. Una sola superficie suave por pantalla (§12). */}
      <LivingField variant="network" modeId={activeMode} />

      <article className="mx-auto flex w-full max-w-[680px] flex-col gap-8 px-6 pb-16 pt-6">
        <Link
          href="/memoria"
          className="-ml-2 inline-flex w-fit items-center gap-1 rounded-[var(--radius-md)] px-2 py-1.5 text-button text-[var(--color-ink-soft)] transition-colors duration-[var(--duration-fast)] hover:text-[var(--color-ink)]"
        >
          <Icon name="atras" size={20} />
          Memoria
        </Link>

        <header className="flex flex-col gap-5">
          <span className="inline-flex w-fit items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] px-3 py-1 text-caption text-[var(--color-ink-soft)]">
            <Icon name={layerInfo.icon} size={14} className="text-[var(--color-memory)]" />
            {layerInfo.label}
          </span>
          <h1 className="text-title text-balance text-[var(--color-ink-deep)]">{p.quote}</h1>
          {p.note ? (
            <p className="text-body-sm max-w-[60ch] border-l-2 border-[var(--color-border)] pl-4 text-[var(--color-ink-soft)]">
              {p.note}
            </p>
          ) : null}
        </header>

        {p.fromSession ? (
          <section className="flex flex-col gap-2">
            <h2 className="text-caption text-[var(--color-ink-soft)]">Contexto</h2>
            <p className="text-body max-w-[60ch] text-[var(--color-ink-soft)]">
              Esto surgió en una conversación con Ynara.
            </p>
          </section>
        ) : null}

        <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
          <div className="flex flex-col gap-1">
            <dt className="text-caption text-[var(--color-ink-soft)]">Fecha</dt>
            <dd className="text-body-sm tabular-nums text-[var(--color-ink)]">
              {formatFullDate(p.dateIso)}
            </dd>
          </div>
          {p.meta.map((row) => (
            <div key={row.label} className="flex flex-col gap-1">
              <dt className="text-caption text-[var(--color-ink-soft)]">{row.label}</dt>
              <dd className="text-body-sm text-[var(--color-ink)]">{row.value}</dd>
            </div>
          ))}
        </dl>

        {p.tags.length > 0 ? (
          <section className="flex flex-col gap-3">
            <h2 className="text-caption text-[var(--color-ink-soft)]">Detalles</h2>
            <ul className="flex flex-wrap gap-2">
              {p.tags.map((tag) => (
                <li
                  key={tag}
                  className="rounded-[var(--radius-pill)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1 text-body-sm text-[var(--color-ink-soft)]"
                >
                  {tag}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {actions ? <div className="flex flex-wrap gap-3">{actions}</div> : null}

        {p.fromSession ? (
          <section className="flex flex-col gap-3 border-t border-[var(--color-border)] pt-6">
            <h2 className="text-caption text-[var(--color-ink-soft)]">Relacionado</h2>
            {relatedPending ? (
              <p className="text-body-sm text-[var(--color-ink-soft)]">
                Buscando recuerdos cercanos…
              </p>
            ) : related.length === 0 ? (
              <p className="text-body-sm text-[var(--color-ink-soft)]">
                Nada más de esta conversación, por ahora.
              </p>
            ) : (
              <ul className="flex flex-col divide-y divide-[var(--color-border)]">
                {related.map((entry, i) => (
                  <TimelineEntryRow
                    key={`${entry.layer}:${entry.ref}`}
                    entry={entry}
                    now={now}
                    index={i}
                  />
                ))}
              </ul>
            )}
          </section>
        ) : null}
      </article>
    </div>
  );
}
