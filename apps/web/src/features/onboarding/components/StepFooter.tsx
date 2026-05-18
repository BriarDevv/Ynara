import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

type Props = {
  /** Si está presente, muestra un botón "Atrás" ghost. */
  onBack?: () => void;
  backLabel?: string;
  /** Acción principal — se le pasa el handler del form. */
  onNext?: () => void;
  nextLabel?: string;
  /** Para mutations en vuelo. */
  loading?: boolean;
  /** El botón CTA puede ser un submit (form binding). */
  nextType?: "button" | "submit";
  /** Hace al CTA disabled. La validación inline en submit es preferida
   *  (ver §4.8 del plan), pero para casos extremos (sin contenido) sí. */
  nextDisabled?: boolean;
  /** Slot para botón de form externo (e.g. dentro de RHF). */
  customNext?: React.ReactNode;
  className?: string;
};

export function StepFooter({
  onBack,
  backLabel = "Atrás",
  onNext,
  nextLabel = "Seguir",
  loading = false,
  nextType = "button",
  nextDisabled = false,
  customNext,
  className,
}: Props) {
  return (
    <div className={cn("flex flex-col gap-3 sm:flex-row sm:items-center", className)}>
      {onBack ? (
        <Button variant="ghost" onClick={onBack} disabled={loading}>
          {backLabel}
        </Button>
      ) : null}
      <div className="flex-1" />
      {customNext ?? (
        <Button
          variant="primary"
          type={nextType}
          onClick={onNext}
          disabled={loading || nextDisabled}
          fullWidth
          className="sm:w-auto sm:min-w-[200px]"
        >
          {loading ? "Un momento…" : nextLabel}
        </Button>
      )}
    </div>
  );
}
