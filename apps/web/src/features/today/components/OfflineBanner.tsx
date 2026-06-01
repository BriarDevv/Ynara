"use client";

import { Icon } from "@ynara/ui";
import { useSyncExternalStore } from "react";

function subscribe(onChange: () => void): () => void {
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

const getSnapshot = () => navigator.onLine;
// SSR / primer render: asumimos online (no hay `navigator`); el cliente corrige
// al montar. Evita un flash del banner en el server.
const getServerSnapshot = () => true;

/**
 * Banner "Sin conexión · trabajando local" (wireframe 16). Ynara funciona
 * local, así que perder la red no es un error: es un estado informado y calmo.
 * Se suscribe a `online`/`offline` vía `useSyncExternalStore` (SSR-safe) y sólo
 * aparece cuando no hay conexión.
 */
export function OfflineBanner() {
  const online = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  if (online) return null;

  return (
    <div
      role="status"
      className="flex items-center gap-2.5 rounded-[var(--radius-md)] bg-[var(--color-bg-soft)] px-4 py-2.5"
    >
      <span aria-hidden className="shrink-0 text-[var(--color-ink-muted)]">
        <Icon name="conexion" size={18} />
      </span>
      <span className="text-body-sm text-[var(--color-ink-soft)]">
        Sin conexión · trabajando local
      </span>
    </div>
  );
}
