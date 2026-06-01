"use client";

import { MemoryLayerSchema } from "@ynara/shared-schemas";
import Link from "next/link";
import { useState } from "react";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { ApiError } from "@/lib/api";
import { useMemoryDetail, useMemoryRelated } from "../api";
import { MemoryDetailSkeleton } from "./MemoryDetailSkeleton";
import { MemoryDetailView } from "./MemoryDetailView";

/** Estado terminal con back link a la lista (capa inválida o ref inexistente). */
function NotFound({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="mx-auto flex w-full max-w-[680px] flex-col gap-6 px-6 pb-16 pt-6">
      <Link
        href="/memoria"
        className="text-button text-[var(--color-ink-soft)] underline underline-offset-4 hover:text-[var(--color-ink)]"
      >
        ← Volver a Memoria
      </Link>
      <EmptyStateCard title={title} hint={hint} />
    </div>
  );
}

/**
 * Dispatcher cliente del detalle de memoria. Valida la capa (que llega por query
 * `?capa=`), pide el detalle (`GET /v1/memory/{layer}/{ref}`) y los relacionados,
 * y resuelve los estados: capa inválida / 404 (recuerdo inexistente o ajeno —
 * mismo trato, sin oráculo) / error real / cargando / detalle.
 */
export function MemoryDetailRoute({
  memoryRef,
  rawLayer,
}: {
  memoryRef: string;
  rawLayer: string | undefined;
}) {
  const parsedLayer = MemoryLayerSchema.safeParse(rawLayer);
  const [now] = useState(() => new Date());

  // Hooks siempre se llaman (regla de hooks); con capa inválida quedan
  // deshabilitados vía una capa centinela que nunca se consulta.
  const layer = parsedLayer.success ? parsedLayer.data : "semantic";
  const detail = useMemoryDetail(layer, memoryRef);
  const related = useMemoryRelated(layer, detail.data);

  if (!parsedLayer.success) {
    return (
      <NotFound
        title="Este enlace no es válido"
        hint="No sabemos de qué tipo de recuerdo se trata. Volvé a la lista y entrá de nuevo."
      />
    );
  }

  if (detail.isPending) return <MemoryDetailSkeleton />;

  if (detail.isError) {
    if (detail.error instanceof ApiError && detail.error.status === 404) {
      return (
        <NotFound
          title="No encontramos este recuerdo"
          hint="Puede que se haya borrado. Volvé a la lista para ver lo que hay."
        />
      );
    }
    return (
      <NotFound
        title="No pudimos abrir este recuerdo"
        hint="Puede ser un problema de conexión. Volvé e intentá de nuevo."
      />
    );
  }

  return (
    <MemoryDetailView
      layer={layer}
      item={detail.data}
      related={related.data ?? []}
      relatedPending={related.isPending}
      now={now}
    />
  );
}
