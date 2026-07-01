"use client";

import { useRef } from "react";
import { problem } from "@/content/ynara";
import { gsap, reducedMotion, registerGsap, useGSAP } from "@/lib/motion";
import "./Problem.css";

/**
 * Capítulo Problema — la animación ES el mensaje (casi sin texto). Escenario
 * sticky sobre la seda; al scrollear, las OCHO apps dispersas en una fila
 * COLAPSAN hacia el centro y se funden en UNA — Ynara. El 8 → 1 se ve.
 * Scrub sin pin (sticky + ScrollTrigger.scrub) → no toca la coordinación del
 * pin horizontal vecino. Reduced-motion: versión estática legible (CSS).
 *
 * Centrado de la respuesta = flexbox (NO transform xPercent → no se descentra),
 * y oculta por CSS por defecto (sin flash; reduced-motion la muestra en flujo).
 */
export function Problem() {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const root = ref.current;
      if (!root || reducedMotion()) return; // CSS deja la versión estática
      registerGsap();

      const track = root.querySelector<HTMLElement>(".pb-track");
      const headline = root.querySelector<HTMLElement>(".pb-headline");
      const answer = root.querySelector<HTMLElement>(".pb-answer");

      // estados iniciales EXPLÍCITOS (la respuesta arranca oculta; las apps, plenas)
      gsap.set(headline, { opacity: 1, y: 0 });
      gsap.set(track, { scaleX: 1, opacity: 1 });
      gsap.set(answer, { opacity: 0, scale: 0.9 });

      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: root,
          start: "top top",
          end: "bottom bottom",
          scrub: true,
        },
        defaults: { ease: "none" },
      });

      // las 8 colapsan al centro (scaleX→0) y se desvanecen; el titular se va…
      tl.to(headline, { opacity: 0, y: -28, duration: 0.32 }, 0.14)
        .to(track, { scaleX: 0.03, opacity: 0, ease: "power2.in", duration: 0.4 }, 0.18)
        // …y en su lugar emerge "Ynara es una." (centrada por flexbox)
        .to(answer, { opacity: 1, scale: 1, ease: "power2.out", duration: 0.4 }, 0.52)
        .to({}, { duration: 0.1 });
    },
    { scope: ref },
  );

  return (
    <section ref={ref} className="pb relative" aria-label={problem.eyebrow}>
      <div className="pb-stage">
        <p className="pb-eyebrow u-tag">{problem.eyebrow}</p>
        <div className="pb-morph">
          <div className="pb-before">
            <h2 className="pb-headline">{problem.problemLine}</h2>
            <ul className="pb-track">
              {problem.apps.map((a) => (
                <li className="pb-chip" key={a}>
                  {a}
                </li>
              ))}
            </ul>
          </div>
          {/* Capa visual del morph (no es heading): la versión accesible va en el
              sr-only de abajo para que el remate llegue a lectores de pantalla. */}
          <div className="pb-answer" aria-hidden>
            <span className="pb-answer-text">
              Ynara es <em className="pb-em">una.</em>
            </span>
          </div>
          <p className="sr-only">{problem.answerLine}</p>
        </div>
      </div>
    </section>
  );
}
