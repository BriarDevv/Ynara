import type { Metadata } from "next";

export const metadata: Metadata = { title: "Audit Log" };

/**
 * F1.5 — Audit Log · ruta "/audit" (blueprint §3). STUB de cimientos: header
 * editorial + placeholder. La composición real (AuditFilters sticky, AuditTable
 * + AuditRow con paginación limit/offset sobre `useAudit(filters, page, range)`)
 * se monta en F1. Vista soberana: nunca hash de integridad ni contenido
 * descifrado — esos campos se omiten ya en el schema Zod, no sólo en el render.
 */
export default function AuditPage() {
  return (
    <section className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <p className="text-caption text-[var(--color-ink-soft)]">Soberanía</p>
        <h1 className="text-display text-[var(--color-ink-deep)]">Audit Log</h1>
        <p className="max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
          Vista soberana del registro de operaciones — sin hash de integridad ni contenido
          descifrado. Filtrable por operación, capa, modo y modelo.
        </p>
      </header>

      <div className="flex min-h-64 items-center justify-center rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border)] bg-[var(--color-bg-soft)]/40 p-8">
        <p className="text-body-sm text-[var(--color-ink-soft)]">Próximamente F1</p>
      </div>
    </section>
  );
}
