"use client";

import "./Trust.css";
import { useRef } from "react";
import { memory } from "@/content/ynara";
import { gsap, reducedMotion, registerGsap, useGSAP } from "@/lib/motion";
import { lineReveal } from "@/lib/reveal";

/**
 * Capítulo Privacidad — el beat de confianza. MUNDO CLARO (ivory). Layout
 * distintivo: statement grande arriba + un LEDGER NUMERADO (01/02/03) que se
 * dibuja fila por fila (números masivos + reglas que crecen). No es una grilla.
 */
export function Trust() {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const root = ref.current;
      if (!root || reducedMotion()) return;
      registerGsap();

      const eyebrow = root.querySelector<HTMLElement>(".tr-eyebrow");
      const statement = root.querySelector<HTMLElement>(".tr-statement");
      const support = root.querySelector<HTMLElement>(".tr-support");
      const rows = gsap.utils.toArray<HTMLElement>(root.querySelectorAll(".tr-row"));
      const chips = root.querySelector<HTMLElement>(".tr-chips");

      if (eyebrow) {
        gsap.set(eyebrow, { opacity: 0, y: 14 });
        gsap.to(eyebrow, {
          opacity: 1,
          y: 0,
          duration: 0.8,
          ease: "power3.out",
          scrollTrigger: { trigger: root, start: "clamp(top 78%)" },
        });
      }
      if (statement) lineReveal(statement, { y: "150%", rot: 2.5, dur: 1.2, stagger: 0.14 });
      if (support)
        lineReveal(support, { y: "140%", rot: 2, dur: 1, stagger: 0.08, start: "clamp(top 74%)" });

      for (const row of rows) {
        const line = row.querySelector<HTMLElement>(".tr-row-line");
        if (line) {
          gsap.set(line, { scaleX: 0, transformOrigin: "left center" });
          gsap.to(line, {
            scaleX: 1,
            duration: 1.1,
            ease: "power3.inOut",
            scrollTrigger: { trigger: row, start: "clamp(top 88%)" },
          });
        }
        const bits = row.querySelectorAll<HTMLElement>(".tr-num, .tr-row-title, .tr-row-body");
        gsap.set(bits, { opacity: 0, y: 22 });
        gsap.to(bits, {
          opacity: 1,
          y: 0,
          duration: 0.8,
          ease: "power3.out",
          stagger: 0.07,
          scrollTrigger: { trigger: row, start: "clamp(top 86%)" },
        });
      }

      if (chips) {
        gsap.set(chips, { opacity: 0, y: 14 });
        gsap.to(chips, {
          opacity: 1,
          y: 0,
          duration: 0.8,
          ease: "power3.out",
          scrollTrigger: { trigger: chips, start: "clamp(top 90%)" },
        });
      }
    },
    { scope: ref },
  );

  return (
    <section
      ref={ref}
      id="privacidad"
      className="tr relative"
      aria-label="Privacidad"
      data-wipe-tone="ivory"
    >
      <div className="tr-inner">
        <div className="tr-head">
          <p className="tr-eyebrow">{memory.eyebrow}</p>
          <h2 className="tr-statement">{memory.statement}</h2>
          <p className="tr-support">{memory.support}</p>
        </div>

        <div className="tr-ledger">
          {memory.layers.map((l, i) => (
            <div className="tr-row" key={l.title}>
              <span className="tr-row-line" aria-hidden />
              <span className="tr-num">{`0${i + 1}`}</span>
              <h3 className="tr-row-title">{l.title}</h3>
              <p className="tr-row-body">{l.body}</p>
            </div>
          ))}
        </div>

        <p className="tr-chips">{memory.privacy.join("  ·  ")}</p>
      </div>
    </section>
  );
}
