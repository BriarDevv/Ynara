"use client";

import { type ReactNode, useRef } from "react";
import { gsap, useGSAP } from "@/lib/gsap";
import { useA11yStore } from "@/stores/a11y";

/**
 * `HeroReveal` — el **momento-firma** de la entrada de una vista (DESIGN.md
 * §8.3 / §16 #7): revela sus hijos marcados con `data-hero-reveal` con un
 * stagger sutil (fade + rise) al montar. Es la única secuencia GSAP de la app;
 * el resto del movimiento es CSS (§8.2) o el campo vivo (§2).
 *
 * Gating de reduced-motion en dos capas, que espejan la cascada de globals.css:
 *  - el **override del store** de a11y gana sobre el OS-pref: `reduce` corta
 *    todo, `normal` anima siempre, `auto` delega en el OS;
 *  - `gsap.matchMedia` resuelve la parte de OS-pref de `auto` y la revierte
 *    sola si la preferencia cambia en runtime.
 * `useGSAP` revierte el contexto (y nuestro `mm.revert()`) al desmontar o al
 * cambiar `motion`, así no quedan tweens colgados (mismo cuidado que los rAF).
 *
 * Sin animación los hijos quedan en su estado natural (no se aplica el
 * `from`), así que bajo reduce no hay flash ni contenido oculto.
 */
export function HeroReveal({ className, children }: { className?: string; children: ReactNode }) {
  const scope = useRef<HTMLDivElement>(null);
  const motion = useA11yStore((s) => s.motion);

  useGSAP(
    () => {
      if (motion === "reduce") return;
      const mm = gsap.matchMedia();
      // `normal` ignora el OS (anima siempre); `auto` sigue el OS-pref.
      const query = motion === "normal" ? "all" : "(prefers-reduced-motion: no-preference)";
      mm.add(query, () => {
        gsap.from("[data-hero-reveal]", {
          autoAlpha: 0,
          y: 16,
          duration: 0.5,
          ease: "power2.out",
          stagger: 0.08,
          // Limpiar los estilos inline que deja el tween: el estado final es
          // el natural del CSS, no un inline que pise themes/responsive.
          clearProps: "opacity,visibility,transform",
        });
      });
      return () => mm.revert();
    },
    { scope, dependencies: [motion] },
  );

  return (
    <div ref={scope} className={className}>
      {children}
    </div>
  );
}
