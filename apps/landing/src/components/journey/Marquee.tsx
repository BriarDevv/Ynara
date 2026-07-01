"use client";

import { useRef } from "react";
import { reducedMotion, useGSAP } from "@/lib/motion";
import "./Marquee.css";

/**
 * Banda MARQUEE — la entrada al MUNDO CLARO (wipe ivory que se desliza por
 * encima de la cola del pin horizontal). Firma tiwis: tipografía masiva en
 * loop horizontal. Rompe el patrón editorial; aporta escala + movimiento.
 * Una fila llena (navy sólido) y otra en outline → ritmo, no monotonía.
 */

const WORDS = ["Organiza", "Recuerda", "Acompaña"];

function Row({ outline }: { outline?: boolean }) {
  // Duplico el contenido 2x para un loop sin costura.
  const seq = [...WORDS, ...WORDS];
  return (
    <div className={`mq-row${outline ? " mq-row--outline" : ""}`}>
      <div className="mq-track" aria-hidden>
        {seq.map((w, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: secuencia estática duplicada
          <span className="mq-word" key={i}>
            {w}
            <span className="mq-dot">●</span>
          </span>
        ))}
      </div>
    </div>
  );
}

export function Marquee() {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const root = ref.current;
      if (!root || reducedMotion()) return;
      // El loop es CSS (keyframes); acá sólo pausamos fuera de viewport por perf.
      const tracks = root.querySelectorAll<HTMLElement>(".mq-track");
      const io = new IntersectionObserver(
        (entries) => {
          for (const e of entries) {
            (e.target as HTMLElement).style.animationPlayState = e.isIntersecting
              ? "running"
              : "paused";
          }
        },
        { threshold: 0 },
      );
      tracks.forEach((t) => {
        io.observe(t);
      });
      return () => io.disconnect();
    },
    { scope: ref },
  );

  return (
    <section
      ref={ref}
      className="mq"
      aria-label="Lo que hace Ynara"
      data-wipe-tone="ivory"
      data-field-cover
    >
      {/* Copia accesible para lectores de pantalla: los tracks visuales son aria-hidden */}
      <p className="sr-only">{WORDS.join(", ")}</p>
      <Row />
      <Row outline />
    </section>
  );
}
