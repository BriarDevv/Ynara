import type { Metadata } from "next";
import { UsersView } from "@/features/users/components/UsersView";

export const metadata: Metadata = { title: "Usuarios & Actividad" };

/**
 * F1.2 — Usuarios & Actividad · ruta "/usuarios" (blueprint §3).
 *
 * Server component: header editorial estático + `metadata`, delega la
 * composición de datos a `<UsersView/>` (client, consume `useUsers()` con el
 * `range` global del topbar). Honestidad de dato (regla #6): los proxies
 * (actividad por sesiones, conversión estimada, heatmap) van rotulados en cada
 * pieza; el schema clava los flags `isApproximate`/`isEstimate` como literales.
 */
export default function UsuariosPage() {
  return (
    <section className="flex flex-col gap-8">
      <header className="anim-fade-in flex flex-col gap-2">
        <p className="text-caption text-[var(--color-ink-soft)]">Producto</p>
        <h1 className="text-display text-[var(--color-ink-deep)]">Usuarios &amp; Actividad</h1>
        <p className="max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
          Actividad aproximada por sesiones (DAU/WAU/MAU), heatmap de uso, conversión de efímeros y
          altas por día.
        </p>
      </header>

      <UsersView />
    </section>
  );
}
