import type { Metadata } from "next";

export const metadata: Metadata = { title: "Modos" };

/**
 * F1.3 — Modos · ruta "/modos" (blueprint §3). STUB de cimientos: header
 * editorial + placeholder. La composición real (ModeMix con ModeDonut,
 * ModeDuration con ModeBarChart, ModeCardStrip de los 5 modos sobre
 * `useModes(range)`) se monta en F1 — acá cantan los 5 tints oficiales.
 */
export default function ModosPage() {
  return (
    <section className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <p className="text-caption text-[var(--color-ink-soft)]">Producto</p>
        <h1 className="text-display text-[var(--color-ink-deep)]">Modos</h1>
        <p className="max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
          Mix de sesiones por modo y duración media por modo (sólo sesiones cerradas), con los cinco
          tints oficiales de marca.
        </p>
      </header>

      <div className="flex min-h-64 items-center justify-center rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border)] bg-[var(--color-bg-soft)]/40 p-8">
        <p className="text-body-sm text-[var(--color-ink-soft)]">Próximamente F1</p>
      </div>
    </section>
  );
}
