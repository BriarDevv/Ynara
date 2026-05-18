import { cn } from "@/lib/cn";
import { MODE_BY_ID, type ModeId } from "./modes";

type Props = {
  modeId: ModeId;
  title: string;
  subtitle?: string;
  onClick?: () => void;
  className?: string;
};

export function SuggestionCard({ modeId, title, subtitle, onClick, className }: Props) {
  const mode = MODE_BY_ID[modeId];
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group relative flex w-full flex-col gap-3 overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)] p-5 text-left transition-[transform,box-shadow,border-color] duration-[var(--duration-base)] ease-[var(--ease-out-soft)] hover:-translate-y-[1px] hover:border-[var(--color-border-strong)] hover:shadow-soft",
        className,
      )}
    >
      {/* Tint sutil arriba — barra de 3px con el gradient del modo */}
      <span aria-hidden className={cn("absolute inset-x-0 top-0 h-[3px]", mode.gradientClass)} />
      <span className="flex items-center gap-2">
        <span
          aria-hidden
          className={cn("h-2 w-2 rounded-[var(--radius-pill)]", mode.gradientClass)}
        />
        <span className="text-caption text-[var(--color-ink-muted)]">{mode.label}</span>
      </span>
      <span className="text-subtitle text-[var(--color-ink)]">{title}</span>
      {subtitle ? (
        <span className="text-body-sm text-[var(--color-ink-soft)]">{subtitle}</span>
      ) : null}
    </button>
  );
}
