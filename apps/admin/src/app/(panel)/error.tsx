"use client";

import { Icon } from "@ynara/ui";
import Link from "next/link";
import { useEffect } from "react";
import { Button } from "@/components/ui/Button";

/**
 * Error boundary del route group `(panel)`: captura cualquier error de render en
 * las 6 pantallas y muestra un fallback editorial en vez de una pantalla rota.
 * Se renderiza DENTRO del `AdminShell` del layout (el chrome se conserva).
 * `reset()` re-monta el segmento; el link a "/" (Overview) es la salida si el
 * reintento no alcanza.
 *
 * Next exige que `error.tsx` sea client component y reciba `error` + `reset`. El
 * detalle crudo NO se muestra al operador (puede traer datos sensibles): va al
 * log/Sentry vía `console.error`.
 */
export default function PanelError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-1 flex-col items-center justify-center gap-4 px-6 py-16 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--color-bg-soft)] text-[var(--color-ink-soft)]">
        <Icon name="foco" size={28} />
      </span>
      <h1 className="text-title text-[var(--color-ink)]">Algo no salió como esperábamos</h1>
      <p className="max-w-[44ch] text-body text-[var(--color-ink-soft)]">
        Hubo un problema al cargar esta pantalla del panel. Probá de nuevo; si persiste, volvé al
        Overview.
      </p>
      <div className="mt-2 flex items-center gap-3">
        <Button onClick={reset}>Reintentar</Button>
        <Link
          href="/"
          className="text-button px-1 py-1 text-[var(--color-ink-soft)] underline decoration-[var(--color-ink-faint)] underline-offset-4 hover:text-[var(--color-ink)]"
        >
          Volver al Overview
        </Link>
      </div>
    </div>
  );
}
