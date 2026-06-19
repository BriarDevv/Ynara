import type { Metadata } from "next";
import { SystemView } from "@/features/system/components/SystemView";

export const metadata: Metadata = { title: "System Health" };

/**
 * F1.6 — System Health · ruta "/sistema" (blueprint §3).
 *
 * Server component: header editorial estático + `metadata`, delega la
 * composición de datos a `<SystemView/>` (client, consume `useSystem()`). NO
 * lleva `range` —es runtime/config, foto única—: guard anti-prod prominente,
 * estado de Postgres/Redis con latencias, e inventario de runtime.
 *
 * Mapeo de estado (decisión de marca): OK = azul plano, down = `--color-error`.
 * Sin verde.
 */
export default function SistemaPage() {
  return (
    <section className="flex flex-col gap-8">
      <header className="anim-fade-in flex flex-col gap-2">
        <p className="text-caption text-[var(--color-ink-soft)]">Soberanía</p>
        <h1 className="text-display text-[var(--color-ink-deep)]">System Health</h1>
        <p className="max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
          Guard anti-prod, estado de Postgres y Redis con latencias, e inventario de runtime
          (modelos, modos, schema head, embedder/reranker).
        </p>
      </header>

      <SystemView />
    </section>
  );
}
