"use client";

import "./VoiceChapter.css";
import { useRef } from "react";
import { feel } from "@/content/ynara";
import { gsap, reducedMotion, registerGsap, useGSAP } from "@/lib/motion";
import { lineReveal } from "@/lib/reveal";

/**
 * Capítulo Demo — "Cómo se siente". MUNDO CLARO (ivory). Layout distintivo:
 * split editorial a la izquierda + un PANEL de chat (mockup del producto) a la
 * derecha donde la conversación se arma sola. No es una grilla de columnas.
 */

// Acentos por pilar, alineados con HorizontalModes (Productividad/Memoria/Bienestar).
const MODE_ACC: Record<string, string> = {
  Productividad: "#2f5aa6",
  Memoria: "#8165a3",
  Bienestar: "#5c6fb3",
};

export function VoiceChapter() {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const root = ref.current;
      if (!root || reducedMotion()) return;
      registerGsap();

      const eyebrow = root.querySelector<HTMLElement>(".vc-eyebrow");
      const hairline = root.querySelector<HTMLElement>(".vc-hairline");
      const title = root.querySelector<HTMLElement>(".vc-title");
      const lead = root.querySelector<HTMLElement>(".vc-lead");

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
      if (hairline) {
        gsap.set(hairline, { width: "0%" });
        gsap.to(hairline, {
          width: "100%",
          duration: 1,
          ease: "power3.inOut",
          scrollTrigger: { trigger: root, start: "clamp(top 76%)" },
        });
      }
      if (title) lineReveal(title, { y: "150%", rot: 2.5, dur: 1.2, stagger: 0.15 });
      if (lead)
        lineReveal(lead, { y: "140%", rot: 2, dur: 1, stagger: 0.1, start: "clamp(top 72%)" });

      // El panel: la conversación "se escribe sola" — cada mensaje sube en cascada.
      const msgs = gsap.utils.toArray<HTMLElement>(root.querySelectorAll(".vc-msg"));
      gsap.set(msgs, { opacity: 0, y: 26 });
      gsap.to(msgs, {
        opacity: 1,
        y: 0,
        duration: 0.7,
        ease: "power3.out",
        stagger: 0.18,
        scrollTrigger: { trigger: ".vc-panel", start: "clamp(top 80%)" },
      });
      const panel = root.querySelector<HTMLElement>(".vc-panel");
      if (panel) {
        gsap.from(panel, {
          y: 40,
          opacity: 0,
          duration: 1,
          ease: "power3.out",
          scrollTrigger: { trigger: panel, start: "clamp(top 82%)" },
        });
      }
    },
    { scope: ref },
  );

  return (
    <section ref={ref} id="voz" className="vc relative" aria-label="La voz" data-wipe-tone="ivory">
      <div className="vc-inner">
        <div className="vc-text">
          <p className="vc-eyebrow">{feel.eyebrow}</p>
          <span className="vc-hairline" aria-hidden />
          <h2 className="vc-title">{feel.title}</h2>
          <p className="vc-lead">{feel.support}</p>
        </div>

        <div className="vc-panel">
          <div className="vc-panel-head">
            <span className="vc-dot-mark" aria-hidden />
            <span className="vc-panel-name">Ynara</span>
            <span className="vc-panel-status">en línea</span>
          </div>
          <div className="vc-thread">
            {feel.chats.map((c) => (
              <div
                className="vc-ex"
                key={c.mode}
                style={{ "--mode-acc": MODE_ACC[c.mode] ?? "#5c6fb3" } as React.CSSProperties}
              >
                <span className="vc-msg vc-mode">{c.mode}</span>
                <p className="vc-msg vc-bubble vc-user">{c.user}</p>
                <p className="vc-msg vc-bubble vc-ynara">{c.ynara}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
