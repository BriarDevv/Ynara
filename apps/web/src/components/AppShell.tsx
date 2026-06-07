"use client";

import { type ReactNode, useRef } from "react";
import { useSmoothScroll } from "@/hooks/useSmoothScroll";
import { MobileTabBar, SidebarNav } from "./AppNav";

/**
 * Cáscara de la app autenticada (build-plan §3.1). Modelo de **viewport
 * fijo con scroll interno** (estilo Claude/ChatGPT), no scroll de documento:
 *
 *  - Outer: `h-[100dvh]` + `overflow-hidden`. Columna en mobile, fila en `lg+`.
 *  - `SidebarNav` (desktop) a la izquierda; `MobileTabBar` (mobile) como
 *    hermano en flujo DEBAJO del `<main>` (no fixed) — así el composer del
 *    chat nunca queda tapado por la tab bar.
 *  - `<main>`: `flex-1 min-h-0 overflow-y-auto`, único landmark de contenido y
 *    **contenedor de scroll** de la app. Las vistas que scrollean (Hoy,
 *    Memoria, Buscar) lo hacen acá adentro; las de altura fija (Chat: `h-full`,
 *    lista interna scrolleable) calzan exacto sin scroll del main. Las páginas
 *    no vuelven a declarar `<main>`.
 *  - **Smooth-scroll** (Lenis, §16 #7): `useSmoothScroll` lo monta sobre el
 *    `<main>` (gateado por reduced-motion, con cleanup). Vive en el shell, no
 *    por-vista; el onboarding tiene su propio layout, así que queda afuera.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const mainRef = useRef<HTMLElement>(null);
  useSmoothScroll(mainRef);

  return (
    <div className="relative isolate flex h-[100dvh] flex-col overflow-hidden bg-[var(--color-bg)] lg:flex-row">
      {/* Skip-link: primer foco tabbable, salta la nav y va directo al
          contenido. Oculto hasta recibir foco de teclado (DESIGN §12). */}
      <a
        href="#contenido"
        className="sr-only focus-visible:not-sr-only focus-visible:absolute focus-visible:left-4 focus-visible:top-4 focus-visible:z-50 focus-visible:rounded-[var(--radius-md)] focus-visible:bg-[var(--color-bg)] focus-visible:px-4 focus-visible:py-2 focus-visible:text-button focus-visible:text-[var(--color-ink)] focus-visible:shadow-lifted"
      >
        Saltar al contenido
      </a>
      <SidebarNav />
      <main
        ref={mainRef}
        id="contenido"
        className="relative flex min-h-0 w-full flex-1 flex-col overflow-y-auto"
      >
        {children}
      </main>
      <MobileTabBar />
    </div>
  );
}
