import type { Metadata } from "next";

export const metadata: Metadata = { title: "Salud del Moat" };

/**
 * F1.4 — Salud del Moat · ruta "/moat" (blueprint §3). Pantalla insignia. STUB
 * de cimientos: header editorial + placeholder. La composición real
 * (MoatHealthHero "latido de la memoria", MoatTower skyline, LayerGrowth,
 * ProceduralHealth, ConsolidationHeartbeat sobre `useMoat(range)`) se monta en
 * F1. Nunca se descifra contenido de memoria — sólo counts y metadata.
 */
export default function MoatPage() {
  return (
    <section className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <p className="text-caption text-[var(--color-ink-soft)]">El Moat</p>
        <h1 className="text-display text-[var(--color-ink-deep)]">Salud del Moat</h1>
        <p className="max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
          El moat: lo que Ynara recuerda, en tres capas (semántica, episódica, procedural). Salud,
          crecimiento y backlog de consolidación.
        </p>
      </header>

      <div className="flex min-h-64 items-center justify-center rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border)] bg-[var(--color-bg-soft)]/40 p-8">
        <p className="text-body-sm text-[var(--color-ink-soft)]">Próximamente F1</p>
      </div>
    </section>
  );
}
