import { Icon } from "@ynara/ui";

type Props = {
  onOpen: () => void;
};

/**
 * CTA "Recap pendiente" (wireframe 06): card oscura full-width que invita a
 * cerrar el día con Ynara. Usa `--color-ink` de fondo + `--color-bg` de texto,
 * así se invierte solo en dark mode. Abre el sheet de recap (Fase E4).
 */
export function RecapCta({ onOpen }: Props) {
  return (
    <button
      type="button"
      onClick={onOpen}
      // Azul plano de marca (alineado a Button primary) en lugar de bg-ink
      // oscuro. El CTA del recap es accion del día — corresponde al color
      // de la marca, no a una superficie nocturna.
      className="group flex w-full items-center gap-4 rounded-[var(--radius-lg)] bg-[var(--color-blue-flat)] p-4 text-left shadow-soft transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:bg-[var(--color-blue-flat-hover)]"
    >
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-caption text-[var(--color-on-dark)] opacity-80">Recap pendiente</span>
        <span className="text-body font-medium text-[var(--color-on-dark)]">
          Cerrá el día con Ynara
        </span>
      </span>
      <span
        aria-hidden
        className="shrink-0 text-[var(--color-on-dark)] opacity-80 transition-opacity duration-[var(--duration-fast)] group-hover:opacity-100"
      >
        <Icon name="chevron" size={20} className="-rotate-90" />
      </span>
    </button>
  );
}
