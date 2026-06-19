/**
 * F1.1 — Overview · ruta "/" (blueprint §3). STUB de cimientos: header editorial
 * (eyebrow + título) + placeholder. La composición real (StatusHero, KpiStrip,
 * AreaTimeSeries, ModeBarChart, AuditPreview sobre `useOverview(range)`) se monta
 * en la fase F1; este stub deja la ruta navegable y tipada sin importar
 * componentes de features que aún no existen.
 */
export default function OverviewPage() {
  return (
    <section className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <p className="text-caption text-[var(--color-ink-soft)]">Panel · Soberanía</p>
        <h1 className="text-display text-[var(--color-ink-deep)]">Overview</h1>
        <p className="max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
          Estado del perímetro, KPIs de producto y un vistazo a la auditoría reciente, en el rango
          temporal elegido.
        </p>
      </header>

      <div className="flex min-h-64 items-center justify-center rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border)] bg-[var(--color-bg-soft)]/40 p-8">
        <p className="text-body-sm text-[var(--color-ink-soft)]">Próximamente F1</p>
      </div>
    </section>
  );
}
