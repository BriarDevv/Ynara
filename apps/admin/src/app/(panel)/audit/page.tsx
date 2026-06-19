import type { Metadata } from "next";
import { AuditScreen } from "@/features/audit/components/AuditScreen";

export const metadata: Metadata = { title: "Audit Log" };

/**
 * F1.5 — Audit Log · ruta "/audit" (blueprint §3).
 *
 * Pantalla soberana del registro de operaciones. Server component que aporta el
 * header editorial + metadata; la composición interactiva (filtros sticky, tabla
 * paginada, banner soberano) vive en `<AuditScreen/>` (client) porque es dueña
 * del estado de filtros/paginación y del rango global.
 *
 * Privacidad estructural (regla #6, "vista soberana"): la fila del audit
 * (`AdminAuditRow`) **omite** `record_hash` y `target_id` del schema Zod. No es
 * que la UI no los pinte: no existen en el tipo, así que aunque el backend los
 * mandara, el `.parse()` del hook los descarta antes de llegar al cliente.
 * Tampoco hay contenido descifrado de memoria en ningún lado de la vista.
 *
 * Page-load escalonado (.anim-stagger-up por banda) + estados loading/empty/error
 * cuidados se resuelven dentro de `AuditScreen`.
 */
export default function AuditPage() {
  return (
    <section className="flex flex-col gap-8">
      <header className="anim-stagger-up flex flex-col gap-2">
        <p className="text-caption text-[var(--color-ink-soft)]">Soberanía</p>
        <h1 className="text-display text-[var(--color-ink-deep)]">Audit Log</h1>
        <p className="max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
          Vista soberana del registro de operaciones — sin hash de integridad ni contenido
          descifrado. Filtrable por operación, capa, modo y modelo.
        </p>
      </header>

      <AuditScreen />
    </section>
  );
}
