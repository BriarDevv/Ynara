import type { ReactNode } from "react";
import { AppNav } from "./AppNav";

/**
 * Cáscara de la app autenticada (build-plan §3.1): la navegación principal
 * (`AppNav`, bottom-tabs mobile / sidebar desktop) + el área de contenido.
 *
 * En mobile el bottom-tab bar va fijo (fuera de flujo), por eso el `<main>`
 * reserva espacio abajo (`pb`) para que el contenido no quede tapado; en
 * `lg+` el sidebar es un hermano en flujo y no hace falta el padding.
 *
 * El `<main>` es el único landmark de contenido principal de la app — las
 * páginas que cuelgan del shell renderizan su contenido sin volver a declarar
 * `<main>`.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative isolate flex min-h-[100dvh] flex-col bg-[var(--color-bg)] lg:flex-row">
      <AppNav />
      <main
        id="contenido"
        className="relative flex min-h-[100dvh] w-full flex-1 flex-col pb-[calc(env(safe-area-inset-bottom)+4.5rem)] lg:pb-0"
      >
        {children}
      </main>
    </div>
  );
}
