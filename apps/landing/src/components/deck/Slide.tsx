"use client";

import type { ReactNode } from "react";
import { useRef } from "react";
import { DECK_SLIDES, REGISTER_ACCENT } from "@/content/deck";
import { cn } from "@/lib/cn";
import { gsap, reducedMotion, useGSAP } from "@/lib/motion";
import { useSlideActive } from "./deck-context";

/**
 * CONTRATO DE LÁMINA. Cada `SlideNN` renderiza:
 *
 *   <Slide index={0}>
 *     <DeckEyebrow>…</DeckEyebrow>
 *     <h1 data-reveal>…</h1>
 *     <p data-reveal>…</p>
 *   </Slide>
 *
 * - `index` (0-based) ⇒ la lámina lee su meta de DECK_SLIDES[index]
 *   (mundo oscuro/marfil, registro, fase del campo). Fuente única.
 * - Mundo: `data-world="dark|ivory"` pinta el fondo (marfil opaco TAPA el campo
 *   = "atenuado"; oscuro lo deja ver).
 * - Registro: setea `--register-accent` (violeta caos/nodos · azul calma) que
 *   usan el diamante del eyebrow y los marcadores.
 * - Entrada: al activarse, los hijos con `[data-reveal]` suben en cascada
 *   (fade-rise, re-ejecutable en cada activación; revertible). Reduced-motion:
 *   sin animación, todo visible (el CSS no esconde nada).
 *   Para coreografías a medida, consumí `useSlideActive(index)` y armá tu propio
 *   useGSAP — no mezcles con `[data-reveal]` sobre los mismos nodos.
 *
 * Sólo la lámina activa está en el árbol de accesibilidad / foco (`inert`).
 */
export function Slide({
  index,
  children,
  className,
  contentClassName,
  backdrop,
}: {
  index: number;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
  /** Capa de fondo a sangre completa, detrás del inner (p.ej. el campo vivo). */
  backdrop?: ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);
  const isActive = useSlideActive(index);
  const meta = DECK_SLIDES[index];

  useGSAP(
    () => {
      const root = ref.current;
      if (!root || !isActive || reducedMotion()) return;
      const items = gsap.utils.toArray<HTMLElement>(root.querySelectorAll("[data-reveal]"));
      if (!items.length) return;
      gsap.set(items, { opacity: 0, y: 28 });
      gsap.to(items, {
        opacity: 1,
        y: 0,
        duration: 0.85,
        ease: "power3.out",
        stagger: 0.09,
        delay: 0.1,
      });
    },
    { scope: ref, dependencies: [isActive], revertOnUpdate: true },
  );

  return (
    <section
      ref={ref}
      className={cn("deck-slide", isActive && "is-active", className)}
      data-world={meta.world}
      data-register={meta.register}
      style={{ "--register-accent": REGISTER_ACCENT[meta.register] } as React.CSSProperties}
      aria-label={`Diapositiva ${meta.id} de ${DECK_SLIDES.length} · ${meta.section}`}
      aria-hidden={!isActive}
      inert={!isActive}
    >
      {backdrop}
      <div className={cn("deck-slide__inner", contentClassName)}>{children}</div>
    </section>
  );
}
