import Link from "next/link";

/**
 * 404 editorial del panel. Sobrio, mismo lenguaje tipográfico que el resto: una
 * superficie acotada, sin caja, con un único camino de vuelta al Overview.
 */
export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-[var(--admin-main)] flex-col justify-center px-8 py-16">
      <p className="text-caption text-[var(--color-ink-soft)]">Error 404</p>
      <h1 className="mt-2 text-hero text-[var(--color-ink-deep)]">Esta ruta no existe</h1>
      <p className="mt-4 max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
        La pantalla que buscás no está en el panel. Puede que el enlace esté roto o que la sección
        todavía no exista.
      </p>
      <Link
        href="/"
        className="text-button mt-8 inline-flex w-fit items-center gap-2 rounded-[var(--radius-md)] bg-[var(--color-blue-flat)] px-6 py-3 text-[var(--color-on-dark)] shadow-soft transition-[background-color] duration-[var(--duration-base)] ease-[var(--ease-out-soft)] hover:bg-[var(--color-blue-flat-hover)] active:bg-[var(--color-blue-flat-active)]"
      >
        Volver al Overview
      </Link>
    </main>
  );
}
