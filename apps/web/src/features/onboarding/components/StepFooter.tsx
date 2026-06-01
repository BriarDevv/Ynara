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
    /*
     * Mobile: column gap-3, CTA primero por orden visual (full-width arriba),
     * Atrás abajo (variant ghost).
     * Desktop: row, Atrás a la izquierda, CTA a la derecha con `ml-auto`.
     * Antes usábamos `<div className="flex-1" />` separator: distribuía
     * los botones a los extremos del card, lo que dejaba sensación de
     * "elementos flotando". `ml-auto` mantiene el CTA pegado al borde
     * derecho sin estirar arbitrariamente la separación.
     */
    <div
      className={cn(
        "flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:gap-4",
        className,
      )}
    >
      {onBack ? (
        /*
         * `self-center` en mobile: el flex-col-reverse parent tiene
         * align-items=stretch por default, lo que expandía "Atrás" como
         * una barra ancha. En desktop el flex-row centra por items así
         * que `sm:self-auto` revierte.
         */
        <Button
          variant="ghost"
          onClick={onBack}
          disabled={loading}
          className="self-center sm:self-auto sm:px-2"
        >
          {backLabel}
        </Button>
      ) : null}
      <div className="sm:ml-auto">
        {customNext ?? (
          <Button
            variant="primary"
            type={nextType}
            onClick={onNext}
            disabled={loading || nextDisabled}
            fullWidth
            className="sm:w-auto sm:min-w-[220px]"
          >
            {loading ? "Un momento…" : nextLabel}
          </Button>
        )}
      </div>
    </div>
  );
}
