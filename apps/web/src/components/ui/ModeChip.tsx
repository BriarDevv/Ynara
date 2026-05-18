import { cn } from "@/lib/cn";
import { MODE_BY_ID, type ModeId } from "./modes";

type Size = "sm" | "md";

type Props = {
  modeId: ModeId;
  /** Por default usa el label canónico del modo. Override si hace falta. */
  label?: string;
  size?: Size;
  className?: string;
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "h-1.5 w-1.5",
  md: "h-2 w-2",
};

const TEXT_BY_SIZE: Record<Size, string> = {
  sm: "text-caption",
  md: "text-body-sm",
};

export function ModeChip({ modeId, label, size = "md", className }: Props) {
  const mode = MODE_BY_ID[modeId];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1",
        TEXT_BY_SIZE[size],
        className,
      )}
    >
      <span
        aria-hidden
        className={cn("rounded-[var(--radius-pill)]", SIZE_CLASSES[size], mode.gradientClass)}
      />
      <span className="text-[var(--color-ink)]">{label ?? mode.label}</span>
    </span>
  );
}
