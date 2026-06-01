import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";

type Props = {
  mode: ModeId;
};

/**
 * Chip del modo activo en el header de Hoy (wireframe 06): un punto con el
 * gradiente del modo + "Modo: {label}". **Display-only** en la Fase E — abrir
 * el switcher (sheet) es la Fase H1; por eso todavía no es un botón ni lleva el
 * chevron del wireframe (no prometemos una acción que no existe).
 */
export function ModeChip({ mode }: Props) {
  const descriptor = MODE_BY_ID[mode];
  return (
    <span className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)] px-3 py-1.5">
      <span
        aria-hidden
        className={`h-2.5 w-2.5 shrink-0 rounded-full ${descriptor.gradientClass}`}
      />
      <span className="text-body-sm text-[var(--color-ink-soft)]">Modo: {descriptor.label}</span>
    </span>
  );
}
