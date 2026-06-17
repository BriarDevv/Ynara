import { Icon } from "@ynara/ui";
import Link from "next/link";
import { cn } from "@/lib/cn";

/**
 * Barra de búsqueda del timeline. No es un input real: es un link con forma de
 * campo que lleva a la vista de Búsqueda (`/buscar`, C3), donde sí se tipea. Así
 * el timeline no carga el estado del buscador y el foco/teclado viven en un solo
 * lugar. Tap target ≥44px (DESIGN §12).
 */
export function MemorySearchLink({ className }: { className?: string }) {
  return (
    <Link
      href="/buscar"
      className={cn(
        // Vidrio sobre el campo vivo (paridad con el buscador real de /buscar):
        // `--color-glass` + blur, borde que se afirma al pasar el cursor.
        "flex min-h-[44px] items-center gap-3 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-glass)] px-4 py-2.5 text-left backdrop-blur-md",
        "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:border-[var(--color-border-strong)]",
        className,
      )}
    >
      <Icon name="buscar" size={20} className="shrink-0 text-[var(--color-ink-soft)]" />
      <span className="text-body text-[var(--color-ink-soft)]">Buscar en tu memoria…</span>
    </Link>
  );
}
