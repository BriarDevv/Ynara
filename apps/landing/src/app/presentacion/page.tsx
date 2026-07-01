import { Deck } from "@/components/deck/Deck";
import { SLIDES } from "@/components/deck/slides";

/**
 * /presentacion — la presentación institucional de lanzamiento (18 láminas en
 * 11 secciones). El chrome de la landing (campo por scroll, Lenis, preloader,
 * nav, footer) se auto-suprime en esta ruta (ver useDeckRoute); el deck monta
 * su propio campo y navega por teclado.
 */
export default function PresentacionPage() {
  return (
    <Deck>
      {SLIDES.map((SlideComponent, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: orden fijo de 18 láminas
        <SlideComponent key={i} index={i} />
      ))}
    </Deck>
  );
}
