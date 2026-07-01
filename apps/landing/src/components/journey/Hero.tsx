"use client";

import { Fragment, useRef } from "react";
import { hero, site } from "@/content/ynara";
import { gsap, reducedMotion, registerGsap, useGSAP } from "@/lib/motion";
import { lineReveal } from "@/lib/reveal";
import "./Hero.css";

/**
 * Capítulo 00 — el héroe sobre la seda (olas edge-on). Composición tiwis: el
 * wordmark "Ynara" COLOSAL anclado abajo, y arriba el valor en una línea + CTA.
 * Tensión diagonal, alto contraste (scrim), mucho aire. No es columna centrada.
 */
function Accented({ text }: { text: string }) {
  return (
    <>
      {text.split("*").map((part, i) =>
        i % 2 === 1 ? (
          // biome-ignore lint/suspicious/noArrayIndexKey: texto estático
          <em key={i} className="hero-accent">
            {part}
          </em>
        ) : (
          // biome-ignore lint/suspicious/noArrayIndexKey: texto estático
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

export function Hero() {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const root = ref.current;
      if (!root || reducedMotion()) return;
      registerGsap();

      const eyebrow = root.querySelector(".hero-eyebrow");
      // Split sólo sobre el wordmark VISIBLE (.hero-wordmark-text), no sobre el
      // <h1> entero: así el <span class="sr-only"> con la propuesta de valor
      // (SEO/a11y) no entra en el SplitText ni rompe el mask de líneas.
      const word = root.querySelector(".hero-wordmark-text");
      const value = root.querySelector<HTMLElement>(".hero-value");
      const aux = gsap.utils.toArray<HTMLElement>(root.querySelectorAll(".hero-aux"));

      gsap.to(root.querySelector(".hero-content"), {
        opacity: 0,
        y: -60,
        ease: "none",
        scrollTrigger: { trigger: root, start: "top top", end: "45% top", scrub: true },
      });

      if (eyebrow) gsap.set(eyebrow, { opacity: 0, y: 18 });
      if (aux.length) gsap.set(aux, { opacity: 0, y: 18 });
      const valueTween = value
        ? lineReveal(value, { y: "130%", rot: 2.2, dur: 1.1, stagger: 0.12, immediate: true })
        : null;
      const wordTween = word
        ? lineReveal(word, { y: "118%", rot: 2, dur: 1.5, stagger: 0, immediate: true })
        : null;

      const play = () => {
        const tlIn = gsap.timeline();
        if (eyebrow) tlIn.to(eyebrow, { opacity: 1, y: 0, duration: 0.8, ease: "power3.out" }, 0);
        tlIn.call(() => valueTween?.play(), undefined, 0.1);
        if (aux.length)
          tlIn.to(aux, { opacity: 1, y: 0, duration: 0.9, ease: "power3.out", stagger: 0.1 }, 0.5);
        tlIn.call(() => wordTween?.play(), undefined, 0.55);
      };

      let introSeen = false;
      try {
        introSeen =
          window.__ynaraIntroDone === true || sessionStorage.getItem("ynara-intro") === "1";
      } catch {
        introSeen = window.__ynaraIntroDone === true;
      }
      let played = false;
      const playOnce = () => {
        if (played) return;
        played = true;
        play();
      };
      if (introSeen) {
        gsap.delayedCall(0.2, playOnce);
        return;
      }
      const onDone = () => playOnce();
      window.addEventListener("ynara:intro-done", onDone, { once: true });
      // Failsafe: si el evento del preloader nunca llega, revelá igual a los ~2.4s
      // → el héroe (LCP) nunca queda oculto/colgado en una conexión lenta.
      const failsafe = gsap.delayedCall(2.4, playOnce);
      return () => {
        window.removeEventListener("ynara:intro-done", onDone);
        failsafe.kill();
      };
    },
    { scope: ref },
  );

  return (
    <section ref={ref} className="hero relative" aria-label="Ynara">
      <div className="hero-content">
        <div className="hero-grid">
          <div className="hero-head">
            <p className="hero-eyebrow">{hero.eyebrow}</p>
            <p className="hero-value">
              <Accented text={hero.value} />
            </p>

            <div className="hero-aux hero-ctas">
              <a className="hero-cta-primary" href={hero.ctaPrimary.href}>
                {hero.ctaPrimary.label}
              </a>
              <a className="hero-cta-secondary" href={hero.ctaSecondary.href}>
                {hero.ctaSecondary.label}
              </a>
            </div>

            <p className="hero-badge hero-aux">{hero.badge}</p>
          </div>
          {/* El <h1> incluye la propuesta de valor para SEO/a11y sin alterar el
              look: "Ynara" sigue siendo lo único visible; el valor va en sr-only. */}
          <h1 className="hero-wordmark">
            <span className="hero-wordmark-text">{site.name}</span>
            <span className="sr-only"> — tu asistente personal con memoria</span>
          </h1>
        </div>
      </div>
    </section>
  );
}
