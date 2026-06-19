import type { ReactNode } from "react";
import { LivingField } from "@/components/ui/LivingField";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

/**
 * Cáscara del panel (blueprint §2.1). Server-friendly wrapper: monta los hijos
 * client (`Sidebar`, `Topbar`) y la atmósfera.
 *
 * Layout: grid de 2 columnas a `lg+` (`248px 1fr`); por debajo de `lg` el rail
 * colapsa a 64px (icon-only — lo resuelve el propio `Sidebar`). El `Topbar` es
 * sticky dentro de la columna de contenido. El `LivingField` va en `-z-field`
 * con profundidad sutil (única atmósfera ambiental del chrome). El `<main>`
 * acota el contenido a `--admin-main` centrado con `px-8`.
 *
 * El contenedor raíz es `relative isolate` para que el LivingField (montado
 * `absolute inset-0`) quede confinado al shell y detrás del contenido.
 */
export function AdminShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative isolate grid min-h-screen grid-cols-[64px_1fr] lg:grid-cols-[248px_1fr]">
      {/* Atmósfera del chrome: profundidad sutil, detrás de todo (--z-field = -10).
          El token ya es negativo, así que se usa sin el prefijo `-z`. */}
      <div aria-hidden className="pointer-events-none fixed inset-0 z-[var(--z-field)]">
        <LivingField variant="depth" density="sutil" />
      </div>

      {/* Columna izquierda: rail de navegación (alto completo, sticky). */}
      <div className="sticky top-0 h-screen">
        <Sidebar />
      </div>

      {/* Columna derecha: topbar sticky + contenido scrolleable. */}
      <div className="flex min-w-0 flex-col">
        <Topbar />
        <main className="mx-auto w-full max-w-[var(--admin-main)] flex-1 px-8 py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
