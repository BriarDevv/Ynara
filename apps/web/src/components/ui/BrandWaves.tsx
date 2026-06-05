import { cn } from "@/lib/cn";

type Props = {
  /**
   * Por default fixed inset-0 -z-10. Si necesitás scope a un container,
   * pasá `absolute` y posicionalo desde el parent.
   */
  variant?: "fixed" | "absolute";
  className?: string;
};

/**
 * Velo de marca para fondos light: ondas violet/blue suaves con glows
 * ambientales. Render del SVG estático `/brand/waves-light.svg` (más
 * liviano que inline y cacheable).
 *
 * Decoración pura: `aria-hidden`, `pointer-events-none`, no recibe focus
 * ni interfiere con el contenido.
 *
 * **Mask de fade-top**: el componente difumina el primer ~28% vertical
 * para que el header del layout respire sobre canvas plano y las ondas
 * solo aparezcan en el cuerpo / pie de la pantalla. Esto evita que el
 * logo + ProgressDots compitan visualmente con el velo.
 *
 * **Stacking**: usa `-z-10` (negativo). Esto vive detrás del flujo normal
 * del documento mientras el body sea el stacking context root. Si algún
 * ancestro establece un nuevo stacking context con `z-index` distinto de
 * `auto`, el BrandWaves quedará atrapado adentro — en ese caso, pasá
 * `variant="absolute"` y usá un container relative.
 */
export function BrandWaves({ variant = "fixed", className }: Props) {
  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none -z-10 select-none overflow-hidden",
        variant === "fixed" ? "fixed inset-0" : "absolute inset-0",
        className,
      )}
      style={{
        // Fade superior: transparente en los primeros 28% y opaco hacia
        // abajo. Mantiene el header limpio sobre canvas ivory.
        WebkitMaskImage: "linear-gradient(to bottom, transparent 0%, black 28%, black 100%)",
        maskImage: "linear-gradient(to bottom, transparent 0%, black 28%, black 100%)",
      }}
    >
      {/* biome-ignore lint/performance/noImgElement: SVG decorativo cacheable, no necesita next/image (no LCP, sin layout shift, sin srcset). */}
      <img
        src="/brand/waves-light.svg"
        alt=""
        className="h-full w-full object-cover"
        draggable={false}
      />
    </div>
  );
}
