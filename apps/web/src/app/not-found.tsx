import { Icon } from "@ynara/ui";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "No encontrado",
};

/**
 * 404 raíz del App Router: se renderiza para rutas sin match o cuando una page
 * llama `notFound()` y no hay un `not-found` más cercano. Hasta ahora no existía
 * ninguno, así que una URL inválida caía en el 404 default de Next (fuera del
 * lenguaje de marca). Server component (puede exportar `metadata`): mensaje
 * editorial + salida a `/hoy`.
 */
export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[var(--color-bg-canvas)] px-6 py-16 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--color-bg-soft)] text-[var(--color-ink-soft)]">
        <Icon name="buscar" size={28} />
      </span>
      <h1 className="text-title text-[var(--color-ink)]">No encontramos esta página</h1>
      <p className="max-w-[40ch] text-body text-[var(--color-ink-soft)]">
        El link puede estar roto o la página se movió.
      </p>
      <Link
        href="/hoy"
        className="text-button px-1 py-1 text-[var(--color-ink-soft)] underline decoration-[var(--color-ink-faint)] underline-offset-4 hover:text-[var(--color-ink)]"
      >
        Volver a Hoy
      </Link>
    </main>
  );
}
