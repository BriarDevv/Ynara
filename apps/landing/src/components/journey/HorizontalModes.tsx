"use client";

import { useRef } from "react";
import { problem } from "@/content/ynara";
import { gsap, reducedMotion, registerGsap, ScrollTrigger, useGSAP } from "@/lib/motion";
import "./HorizontalModes.css";

/**
 * Capítulo 03 — EL HANDOFF. El campo llega aquí convertido en tablero de
 * cuadros grandes (y se atenúa); el mundo de cards ivory CRECE desde la
 * esquina inferior derecha sobre él, se asienta, y el scroll pasa a ser
 * HORIZONTAL: tres pilares como cards de 50vw alternando espaciadores
 * transparentes donde el campo respira. Mecánica tiwis exacta:
 * pin + scale(0→1, origin 100% 100%) 30% → settle 20% → travel 50% → hold 15%.
 *
 * `data-cascade-end` en la sección = el punto donde el timeline del campo
 * completa (p=1). El tablero ES la antesala de las cards.
 */

// Acentos planos de la identidad: azul · violeta (señal=memoria) · azul violáceo · índigo.
const ACCENTS = ["#2f5aa6", "#8165a3", "#5c6fb3", "#434a82"] as const;
const CLAIMS = [
  "Agendar, recordar, cerrar tareas. Ynara aprende cómo trabajás y se adelanta — lista antes de que preguntes.",
  "Nombres, charlas, decisiones. Todo se conecta en silencio y se cita textual: no reescribe tus recuerdos.",
  "Registra tu energía y tus patrones. Está cuando la necesitás y se corre cuando no.",
  "Conecta lo que sabe de vos para sugerir el próximo paso — qué priorizar, cuándo frenar, a quién escribir. Ella propone; vos decidís.",
] as const;
const CARDS = problem.layers.map((l, i) => ({
  word: l.title,
  label: l.note.replace(/\.$/, ""),
  claim: CLAIMS[i],
  features: l.features,
  accent: ACCENTS[i],
}));

function SvgOrbit({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" className={className} aria-hidden role="presentation">
      <circle cx="50" cy="50" r="38" />
      <circle cx="50" cy="50" r="18" />
      <line x1="50" y1="12" x2="50" y2="88" />
      <line x1="12" y1="50" x2="88" y2="50" />
    </svg>
  );
}
function SvgNet({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" className={className} aria-hidden role="presentation">
      <circle cx="50" cy="50" r="40" />
      <line x1="10" y1="50" x2="90" y2="50" />
      <path d="M50 10 Q70 30 50 50 Q30 70 50 90" />
      <path d="M50 10 Q30 30 50 50 Q70 70 50 90" />
    </svg>
  );
}
function SvgPulse({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 60" className={className} aria-hidden role="presentation">
      <polyline points="0,30 15,30 25,10 35,50 45,20 55,40 65,30 80,30 90,30 100,30" />
    </svg>
  );
}
function SvgCompass({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" className={className} aria-hidden role="presentation">
      <circle cx="50" cy="50" r="38" />
      <path d="M50 26 L60 50 L50 74 L40 50 Z" />
      <circle cx="50" cy="50" r="3" />
    </svg>
  );
}

const SPACERS = [
  { label: "01 · Organiza", Svg: SvgOrbit },
  { label: "02 · Recuerda", Svg: SvgNet },
  { label: "03 · Acompaña", Svg: SvgPulse },
  { label: "04 · Aconseja", Svg: SvgCompass },
] as const;

export function HorizontalModes() {
  const rootRef = useRef<HTMLElement>(null);
  const textPinRef = useRef<HTMLDivElement>(null);
  const slideRefs = useRef<(HTMLDivElement | null)[]>([]);
  const revealedRef = useRef<Set<number>>(new Set());
  const firstCardTweenRef = useRef<gsap.core.Tween | null>(null);

  useGSAP(
    () => {
      registerGsap();
      if (reducedMotion()) return; // CSS deja el stack vertical legible

      // Cualquier dispositivo touch (pointer: coarse) usa el stack vertical sin
      // importar el ancho: en tablets touch el pin horizontal secuestraba el
      // scroll vertical. Solo punteros finos (mouse/trackpad) ≥768px obtienen el
      // viaje horizontal. matchMedia re-corre el setup correcto al cruzar el
      // breakpoint (antes se leía una sola vez al montar → rotar/redimensionar
      // dejaba el modo equivocado) y revierte todo (triggers, pin, splits) al
      // cambiar de query o desmontar.
      const mm = gsap.matchMedia();
      mm.add("(max-width: 767px), (pointer: coarse)", () => {
        setupMobileFallback();
      });
      mm.add("(min-width: 768px) and (pointer: fine)", () => setupDesktop());
      return () => mm.revert();
    },
    { scope: rootRef },
  );

  function setupMobileFallback() {
    // Mobile / touch: stack vertical con el contenido SIEMPRE visible. El reveal
    // por scroll es exclusivo del viaje horizontal (desktop). Acá NO escondemos
    // nada y, además, limpiamos ACTIVAMENTE cualquier estilo inline que el viaje
    // horizontal pudiera haber dejado al redimensionar desktop->mobile (los
    // gsap.set(opacity:0)/transform no siempre los revierte matchMedia). clearProps
    // los borra y el contenido vuelve a su estado natural; el CSS !important del
    // breakpoint mobile es la garantía final de visibilidad.
    for (const el of slideRefs.current) {
      if (!el) continue;
      const targets = el.querySelectorAll<HTMLElement>(
        ".h-slide__claim, .h-slide__word, .h-slide__label, .h-slide__features li, .slide-side__label",
      );
      const strokes = el.querySelectorAll<SVGGeometryElement>(
        ".slide-side__svg path, .slide-side__svg circle, .slide-side__svg line, .slide-side__svg polyline",
      );
      gsap.set([...targets, ...strokes], { clearProps: "all" });
    }
  }

  function setupDesktop() {
    const root = rootRef.current;
    if (!root) return;
    const section = root.querySelector<HTMLElement>(".horizontal-section");
    const wrapper = root.querySelector<HTMLElement>(".horizontal-wrapper");
    const track = root.querySelector<HTMLElement>(".track");
    const textPin = textPinRef.current;
    if (!section || !wrapper || !track) return;

    const dist = () => track.scrollWidth - window.innerWidth;

    gsap.set(wrapper, { scale: 0, x: 0, transformOrigin: "100% 100%" });
    gsap.set(track, { x: 0 });

    prepareSlideReveals();

    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: section,
        start: "top top",
        end: () => `+=${dist() + window.innerHeight * 0.5}`,
        scrub: true,
        pin: true,
        anticipatePin: 1,
        invalidateOnRefresh: true,
      },
      defaults: { ease: "none" },
    });

    tl.addLabel("scaleStart")
      // FASE 1 (30%): el mundo de cards crece desde la esquina inferior derecha
      .to(wrapper, { scale: 1, x: "50vw", duration: 0.3 })
      // primer card: claim + label + palabra, gateados al fin de la escala
      .call(
        () => {
          firstCardTweenRef.current?.play();
          const first = slideRefs.current[0];
          if (first) {
            const label = first.querySelector<HTMLElement>(".h-slide__label");
            const word = first.querySelector<HTMLElement>(".h-slide__word");
            const feats = first.querySelectorAll<HTMLElement>(".h-slide__features li");
            if (label)
              gsap.to(label, { opacity: 1, duration: 0.5, ease: "power3.out", delay: 0.1 });
            if (word)
              gsap.to(word, {
                y: "0%",
                opacity: 1,
                duration: 0.9,
                ease: "power3.out",
                delay: 0.15,
              });
            if (feats.length)
              gsap.to(feats, {
                opacity: 1,
                y: 0,
                duration: 0.7,
                ease: "power3.out",
                stagger: 0.07,
                delay: 0.2,
              });
          }
        },
        undefined,
        ">",
      )
      .addLabel("scaleEnd")
      // FASE 2 (20%): settle a x:0
      .to(wrapper, { x: "0vw", duration: 0.2 })
      // FASE 3 (50%): el viaje lateral
      .to(track, { x: () => -dist(), duration: 0.5 })
      // FASE 4 (15%): hold de salida
      .to({}, { duration: 0.15 });

    if (textPin) {
      ScrollTrigger.create({
        trigger: section,
        start: "top 20%",
        end: () => {
          const st = tl.scrollTrigger;
          if (!st) return "+=0";
          const s = st.start + tl.labels.scaleStart * (st.end - st.start);
          const e = st.start + tl.labels.scaleEnd * (st.end - st.start);
          // Desanclar el titular ANTES (0.5 en vez de 0.7) de que la primera card
          // sea legible → el titular no queda solapado con la card que crece.
          return s + (e - s) * 0.5;
        },
        pin: textPin,
        pinSpacing: false,
        scrub: true,
        anticipatePin: 1,
      });
    }

    const observer = setupIntersectionObserver();

    // Reveal del bloque pinneado (viene de abajo, está below-fold al cargar)
    const pinLabel = textPin?.querySelector<HTMLElement>(".hm-pin-label");
    const pinText = textPin?.querySelector<HTMLElement>(".hm-pin-text");
    if (pinLabel) {
      gsap.set(pinLabel, { opacity: 0, y: 14 });
      gsap.to(pinLabel, {
        opacity: 1,
        y: 0,
        duration: 0.8,
        ease: "power3.out",
        scrollTrigger: { trigger: textPin, start: "clamp(top 80%)" },
      });
    }
    if (pinText) {
      gsap.set(pinText, { opacity: 0, y: 20 });
      gsap.to(pinText, {
        opacity: 1,
        y: 0,
        duration: 1,
        ease: "power3.out",
        scrollTrigger: { trigger: textPin, start: "clamp(top 80%)" },
      });
    }

    // cleanup: matchMedia revierte triggers/pin/splits; el IO se desconecta acá.
    return () => observer?.disconnect();
  }

  function prepareSlideReveals() {
    slideRefs.current.forEach((el, i) => {
      if (!el) return;
      const isCard = i % 2 === 0;
      if (isCard) {
        const claim = el.querySelector<HTMLElement>(".h-slide__claim");
        const label = el.querySelector<HTMLElement>(".h-slide__label");
        const word = el.querySelector<HTMLElement>(".h-slide__word");
        const feats = el.querySelectorAll<HTMLElement>(".h-slide__features li");
        if (feats.length) gsap.set(feats, { opacity: 0, y: 14 });
        // Claims: fade simple (opacity + y), sin SplitText. El reveal por
        // líneas enmascaradas dejaba estructuras que no se limpiaban al pasar a
        // mobile (claim con height:0). Un fade es revertible con clearProps/CSS.
        if (claim) gsap.set(claim, { opacity: 0, y: 24 });
        if (i === 0 && claim) {
          // card 0: reveal gateado por el timeline (al terminar la escala).
          firstCardTweenRef.current = gsap.to(claim, {
            opacity: 1,
            y: 0,
            duration: 0.7,
            ease: "power3.out",
            paused: true,
          });
        }
        if (label) gsap.set(label, { opacity: 0 });
        if (word) gsap.set(word, { y: "140%", opacity: 0 });
      } else {
        const paths = el.querySelectorAll<SVGGeometryElement>(
          ".slide-side__svg path, .slide-side__svg circle, .slide-side__svg line, .slide-side__svg polyline",
        );
        paths.forEach((p) => {
          if (p.getTotalLength) {
            const len = p.getTotalLength();
            gsap.set(p, { strokeDasharray: len, strokeDashoffset: len });
          }
        });
        const label = el.querySelector<HTMLElement>(".slide-side__label");
        if (label) gsap.set(label, { opacity: 0, y: "20px" });
      }
    });
  }

  function setupIntersectionObserver() {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const idx = Number((entry.target as HTMLElement).dataset.slideIndex);
          if (Number.isNaN(idx) || revealedRef.current.has(idx)) return;
          revealedRef.current.add(idx);
          observer.unobserve(entry.target);
          revealSlide(idx);
        });
      },
      { threshold: 0.5 },
    );
    slideRefs.current.forEach((el, i) => {
      if (!el || i === 0) return;
      el.dataset.slideIndex = String(i);
      observer.observe(el);
    });
    return observer;
  }

  function revealSlide(idx: number) {
    const el = slideRefs.current[idx];
    if (!el) return;
    const isCard = idx % 2 === 0;

    if (isCard) {
      const claim = el.querySelector<HTMLElement>(".h-slide__claim");
      const label = el.querySelector<HTMLElement>(".h-slide__label");
      const word = el.querySelector<HTMLElement>(".h-slide__word");
      const feats = el.querySelectorAll<HTMLElement>(".h-slide__features li");
      if (claim) gsap.to(claim, { opacity: 1, y: 0, duration: 0.7, ease: "power3.out" });
      if (label) gsap.to(label, { opacity: 1, duration: 0.5, ease: "power3.out", delay: 0.1 });
      if (word)
        gsap.to(word, { y: "0%", opacity: 1, duration: 0.9, ease: "power3.out", delay: 0.15 });
      if (feats.length)
        gsap.to(feats, {
          opacity: 1,
          y: 0,
          duration: 0.7,
          ease: "power3.out",
          stagger: 0.07,
          delay: 0.2,
        });
    } else {
      const paths = el.querySelectorAll<SVGGeometryElement>(
        ".slide-side__svg path, .slide-side__svg circle, .slide-side__svg line, .slide-side__svg polyline",
      );
      paths.forEach((p, pi) => {
        gsap.to(p, { strokeDashoffset: 0, duration: 1.5, ease: "power3.inOut", delay: pi * 0.1 });
      });
      const label = el.querySelector<HTMLElement>(".slide-side__label");
      if (label)
        gsap.to(label, { opacity: 1, y: "0px", duration: 0.7, ease: "power3.out", delay: 0.3 });
    }
  }

  function setSlideRef(idx: number) {
    return (el: HTMLDivElement | null) => {
      slideRefs.current[idx] = el;
    };
  }

  return (
    <section ref={rootRef} id="producto" aria-label="Producto">
      {/* Bloque pinneado: queda quieto mientras el mundo de cards crece encima */}
      <div className="hm-text-pin" ref={textPinRef}>
        <p className="hm-pin-label">{problem.pillarsEyebrow}</p>
        <p className="hm-pin-text">{problem.pillarsIntro}</p>
        <span className="hm-pin-hint" aria-hidden>
          El recorrido sigue al costado
        </span>
      </div>

      {/* La sección horizontal — acá COMPLETA la cascada del campo */}
      <div className="horizontal-section" data-cascade-end>
        <div className="horizontal-wrapper">
          <div className="track">
            {CARDS.map((card, ci) => {
              const spacer = SPACERS[ci];
              const SpacerSvg = spacer.Svg;
              return (
                <div key={card.word} style={{ display: "contents" }}>
                  <div
                    className="h-slide"
                    ref={setSlideRef(ci * 2)}
                    data-wipe-tone="ivory"
                    style={{ "--card-acc": card.accent } as React.CSSProperties}
                  >
                    <div className="h-slide__top">
                      <p className="h-slide__claim">{card.claim}</p>
                      <ul className="h-slide__features">
                        {card.features.map((f) => (
                          <li key={f}>{f}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="h-slide__bot">
                      <span className="h-slide__accent" aria-hidden />
                      <span className="h-slide__label">{card.label}</span>
                      <h2 className="h-slide__word">{card.word}</h2>
                    </div>
                  </div>
                  <div className="h-slide side" ref={setSlideRef(ci * 2 + 1)}>
                    <div className="slide-side__content">
                      <span className="slide-side__label">{spacer.label}</span>
                      <SpacerSvg className="slide-side__svg" />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
