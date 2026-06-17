"use client";

import { Icon } from "@ynara/ui";
import Link from "next/link";
import { useEffect } from "react";
import { Button } from "@/components/ui/Button";

/**
 * Error boundary del route group `(app)`: captura cualquier error de render en
 * las vistas autenticadas (Hoy, Chat, Memoria, …) y muestra un fallback
 * editorial en vez de una pantalla rota. Se renderiza DENTRO del `AppShell` del
 * layout (la nav se conserva). `reset()` re-monta el segmento; el link a `/hoy`
 * es la salida si el reintento no alcanza.
 *
 * Next exige que `error.tsx` sea client component y reciba `error` + `reset`.
 */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // El detalle real va al log del server / Sentry (init en main.tsx). Acá NO
    // se muestra el mensaje crudo al usuario: puede traer datos sensibles.
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-full flex-1 flex-col items-center justify-center gap-4 px-6 py-16 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--color-bg-soft)] text-[var(--color-ink-soft)]">
        <Icon name="foco" size={28} />
      </span>
      <h1 className="text-title text-[var(--color-ink)]">Algo no salió como esperábamos</h1>
      <p className="max-w-[40ch] text-body text-[var(--color-ink-soft)]">
        Tuvimos un problema al cargar esta pantalla. Probá de nuevo; si sigue, volvé a Hoy.
      </p>
      <div className="mt-2 flex items-center gap-3">
        <Button onClick={reset}>Reintentar</Button>
        <Link
          href="/hoy"
          className="text-button px-1 py-1 text-[var(--color-ink-soft)] underline decoration-[var(--color-ink-faint)] underline-offset-4 hover:text-[var(--color-ink)]"
        >
          Volver a Hoy
        </Link>
      </div>
    </div>
  );
}
