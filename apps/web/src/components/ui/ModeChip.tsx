import { cn } from "@/lib/cn";
import { MODE_BY_ID, type ModeId } from "./modes";

type Size = "sm" | "md";
type Variant = "outline" | "soft";

type Props = {
  modeId: ModeId;
  /** Por default usa el label canónico del modo. Override si hace falta. */
  label?: string;
  size?: Size;
  /**
   * outline: pill con borde sobre blanco (default). soft: pill sobre
   * bg-soft, sin borde (header de Hoy).
   */
  variant?: Variant;
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

const VARIANT_CLASSES: Record<Variant, string> = {
  outline: "border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1",
  soft: "bg-[var(--color-bg-soft)] px-3 py-1.5",
};

const LABEL_BY_VARIANT: Record<Variant, string> = {
  outline: "text-[var(--color-ink)]",
  soft: "text-[var(--color-ink-soft)]",
};

export function ModeChip({ modeId, label, size = "md", variant = "outline", className }: Props) {
  const mode = MODE_BY_ID[modeId];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-[var(--radius-pill)]",
        VARIANT_CLASSES[variant],
        TEXT_BY_SIZE[size],
        className,
      )}
    >
      <span
        aria-hidden
        className={cn("shrink-0 rounded-[var(--radius-pill)]", SIZE_CLASSES[size])}
        style={{ backgroundColor: mode.tintVar }}
      />
      <span className={LABEL_BY_VARIANT[variant]}>{label ?? mode.label}</span>
    </span>
  );
}
