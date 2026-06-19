import type { Metadata } from "next";

export const metadata: Metadata = { title: "Usuarios & Actividad" };

/**
 * F1.2 — Usuarios & Actividad · ruta "/usuarios" (blueprint §3). STUB de
 * cimientos: header editorial + placeholder. La composición real (ActivityKpis
 * DAU/WAU/MAU, UsageHeatmap, ConversionFunnel, SignupsTable sobre
 * `useUsers(range)`) se monta en F1.
 */
export default function UsuariosPage() {
  return (
    <section className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <p className="text-caption text-[var(--color-ink-soft)]">Producto</p>
        <h1 className="text-display text-[var(--color-ink-deep)]">Usuarios &amp; Actividad</h1>
        <p className="max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
          Actividad aproximada por sesiones (DAU/WAU/MAU), heatmap de uso, conversión de efímeros y
          altas por día.
        </p>
      </header>

      <div className="flex min-h-64 items-center justify-center rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border)] bg-[var(--color-bg-soft)]/40 p-8">
        <p className="text-body-sm text-[var(--color-ink-soft)]">Próximamente F1</p>
      </div>
    </section>
  );
}
