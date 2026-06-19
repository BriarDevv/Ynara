import type { Metadata } from "next";
import { MoatScreen } from "@/features/moat/components/MoatScreen";

export const metadata: Metadata = { title: "Salud del Moat" };

/**
 * F1.4 — Salud del Moat · ruta "/moat" (blueprint §3). Pantalla insignia.
 *
 * Server component: solo el header editorial (eyebrow → título → subtítulo).
 * Toda la composición data-driven (hero "latido de la memoria", skyline de
 * `MoatTower`, `LayerGrowth`, `ProceduralHealth`, `ConsolidationHeartbeat` sobre
 * `useMoat(range)`) vive en `<MoatScreen/>`, que es client por estado/efectos.
 *
 * Privacidad (regla #6): nunca se descifra contenido de memoria — la pantalla
 * solo muestra counts, deltas, series y metadata de episodios.
 */
export default function MoatPage() {
  return (
    <section className="flex flex-col gap-8">
      <header className="anim-fade-in flex flex-col gap-2">
        <p className="text-caption text-[var(--color-ink-soft)]">El Moat</p>
        <h1 className="text-display text-[var(--color-ink-deep)]">Salud del Moat</h1>
        <p className="max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
          El moat: lo que Ynara recuerda, en tres capas (semántica, episódica, procedural). Salud,
          crecimiento y backlog de consolidación.
        </p>
      </header>

      <MoatScreen />
    </section>
  );
}
