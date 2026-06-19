import type { Metadata } from "next";

export const metadata: Metadata = { title: "System Health" };

/**
 * F1.6 — System Health · ruta "/sistema" (blueprint §3). STUB de cimientos:
 * header editorial + placeholder. La composición real (ProdGuardBanner,
 * StatusCard de Postgres + Redis, RuntimeInventory sobre `useSystem()`, sin
 * `range`) se monta en F1. El mapeo de estado es OK = azul plano, down =
 * `--color-error` (decisión de marca: sin verde).
 */
export default function SistemaPage() {
  return (
    <section className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <p className="text-caption text-[var(--color-ink-soft)]">Soberanía</p>
        <h1 className="text-display text-[var(--color-ink-deep)]">System Health</h1>
        <p className="max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
          Guard anti-prod, estado de Postgres y Redis con latencias, e inventario de runtime
          (modelos, modos, schema head, embedder/reranker).
        </p>
      </header>

      <div className="flex min-h-64 items-center justify-center rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border)] bg-[var(--color-bg-soft)]/40 p-8">
        <p className="text-body-sm text-[var(--color-ink-soft)]">Próximamente F1</p>
      </div>
    </section>
  );
}
