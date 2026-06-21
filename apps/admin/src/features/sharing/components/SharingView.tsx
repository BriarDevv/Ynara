"use client";

import type { CSSProperties, ReactNode } from "react";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { cn } from "@/lib/cn";
import { useConnectivity } from "../hooks/useConnectivity";
import { ShareTargetCard } from "./ShareTargetCard";
import { TailscaleBanner } from "./TailscaleBanner";

/**
 * Composición client de Conexión / Compartir.
 *
 * Vive separada de `page.tsx` (server) para que la ruta conserve `metadata` y el
 * default server-component mientras esta capa —que consume `useConnectivity`— sea
 * la única client. NO lleva `range`: es estado de conectividad, foto única.
 *
 * Grilla 12-col por bandas con reveal escalonado:
 *  1. `TailscaleBanner` (`col-span-12`) — el estado del tailnet, lo primero.
 *  2. N `ShareTargetCard` (`col-span-6`) — las URLs para repartir (panel admin y
 *     app web primero, después API OpenAI-compatible y chat de Open WebUI).
 *
 * Si el tailnet está abajo no hay targets: se muestra un empty editorial con el
 * próximo paso (prender Tailscale en el host), no un error.
 */
export function SharingView() {
  const { data, isPending, isError, refetch } = useConnectivity();

  if (isPending) return <SharingSkeleton />;

  if (isError) {
    return (
      <EmptyStateCard
        title="No pudimos leer el estado de conectividad."
        hint="El probe de /v1/admin/connectivity no respondió. Reintentá en unos segundos."
        action={
          <button
            type="button"
            onClick={() => refetch()}
            className="rounded-[var(--radius-pill)] border border-[var(--color-border-strong)] px-4 py-2 text-button text-[var(--color-ink)] transition-colors duration-[var(--duration-fast)] hover:bg-[var(--color-bg-soft)]"
          >
            Reintentar
          </button>
        }
      />
    );
  }

  if (!data) {
    return (
      <EmptyStateCard
        title="Sin datos de conectividad."
        hint="El endpoint /v1/admin/connectivity devolvió vacío."
      />
    );
  }

  const { tailscale, targets } = data;

  return (
    <div className="grid grid-cols-12 gap-8">
      <Band span={12} index={0}>
        <TailscaleBanner
          up={tailscale.up}
          hostname={tailscale.hostname ?? null}
          tailnetIp={tailscale.tailnet_ip ?? null}
          detail={tailscale.detail}
        />
      </Band>

      {targets.length === 0 ? (
        <Band span={12} index={1}>
          <EmptyStateCard
            title="Todavía no hay nada para compartir."
            hint="Prendé Tailscale en esta máquina (tailscale up) para exponer el serving al tailnet; las URLs aparecen acá."
          />
        </Band>
      ) : (
        targets.map((target, i) => (
          <Band span={6} index={i + 1} key={target.label}>
            <ShareTargetCard label={target.label} url={target.url} port={target.port} />
          </Band>
        ))
      )}
    </div>
  );
}

/** Mapeo de `span` a clase de columna (Tailwind necesita clases estáticas). */
const SPAN_CLASS: Record<6 | 12, string> = {
  6: "col-span-12 lg:col-span-6",
  12: "col-span-12",
};

/**
 * Banda de la grilla de 12 columnas con reveal escalonado de page-load: cada banda
 * entra con `.anim-stagger-up` y su `--stagger-index` (neutralizado bajo
 * reduced-motion por la cascada global).
 */
function Band({ span, index, children }: { span: 6 | 12; index: number; children: ReactNode }) {
  return (
    <div
      className={cn(SPAN_CLASS[span], "anim-stagger-up")}
      style={{ "--stagger-index": index } as CSSProperties}
    >
      {children}
    </div>
  );
}

/** Skeleton con la misma topología (banner + 4 cards) para que el layout no salte. */
function SharingSkeleton() {
  return (
    <div className="grid grid-cols-12 gap-8" aria-hidden>
      <div className="anim-fade-in col-span-12 h-28 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]" />
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="anim-fade-in col-span-12 h-44 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] lg:col-span-6"
        />
      ))}
    </div>
  );
}
