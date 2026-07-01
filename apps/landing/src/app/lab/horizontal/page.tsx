"use client";

import "./page.css";
import { useEffect, useRef } from "react";
import { gsap, reducedMotion, registerGsap, ScrollTrigger, SplitText, useGSAP } from "@/lib/motion";
import { hairlineReveal, lineReveal } from "@/lib/reveal";

/* ─────────────────────────────────────────────
   SVG shapes for spacer slides (3 different motifs)
───────────────────────────────────────────── */
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
function SvgPulse({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 60" className={className} aria-hidden role="presentation">
      <polyline points="0,30 15,30 25,10 35,50 45,20 55,40 65,30 80,30 90,30 100,30" />
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

/* ─────────────────────────────────────────────
   Slide data
───────────────────────────────────────────── */
const CARDS = [
  {
    label: "Tu asistente personal",
    claim:
      "Ynara aprende cómo pensás, cómo trabajás y qué necesitás — para estar lista antes de que preguntes.",
    word: "Productividad",
  },
  {
    label: "Todo lo que importa",
    claim:
      "Captura conversaciones, notas y momentos. Los conecta en silencio para que vos puedas recordar lo que realmente vale.",
    word: "Memoria",
  },
  {
    label: "Presencia equilibrada",
    claim:
      "No solo tareas: Ynara registra tu energía, tus patrones y te ayuda a vivir con intención.",
    word: "Bienestar",
  },
] as const;

const SPACERS = [
  { label: "01 / Flujo", Svg: SvgOrbit },
  { label: "02 / Ritmo", Svg: SvgPulse },
  { label: "03 / Conexión", Svg: SvgNet },
] as const;

/* ─────────────────────────────────────────────
   Main page component
───────────────────────────────────────────── */
export default function HorizontalLabPage() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const introRef = useRef<HTMLDivElement>(null);
  const textPinRef = useRef<HTMLDivElement>(null);
  const exitRef = useRef<HTMLDivElement>(null);

  // Refs for slide reveals (cards + spacers interleaved: card, spacer, card, spacer, card, spacer)
  const slideRefs = useRef<(HTMLDivElement | null)[]>([]);
  // Splits de los claims (cards IO): se parten al preparar, se animan al revelar
  const claimSplitsRef = useRef<Map<number, SplitText>>(new Map());
  // Track which slides have already revealed (IO fire-once)
  const revealedRef = useRef<Set<number>>(new Set());
  // Stored tweens for first-card gated reveal
  const firstCardTweenRef = useRef<gsap.core.Tween | null>(null);

  /* ── Register once ───────────────────────── */
  useEffect(() => {
    registerGsap();
  }, []);

  /* ── Main GSAP scope ─────────────────────── */
  useGSAP(
    () => {
      if (reducedMotion()) {
        // Reduced motion: skip pins/horizontal, do simple reveals
        setupReducedMotion();
        return;
      }

      const isMobile = window.matchMedia("(max-width: 479px)").matches;
      if (isMobile) {
        setupMobileFallback();
        return;
      }

      setupDesktop();
    },
    { scope: sectionRef },
  );

  /* ─────────────────────────────────────────
     REDUCED MOTION path
  ───────────────────────────────────────── */
  function setupReducedMotion() {
    // Static: just make everything visible, no pins or scrub
    if (introRef.current) {
      const manifesto = introRef.current.querySelector(".hl-intro__manifesto");
      if (manifesto) {
        gsap.set(manifesto, { clearProps: "all" });
      }
    }
    slideRefs.current.forEach((el) => {
      if (!el) return;
      const texts = el.querySelectorAll(".h-slide__claim, .h-slide__word, .h-slide__label");
      gsap.set(texts, { clearProps: "all" });
    });
  }

  /* ─────────────────────────────────────────
     MOBILE path (≤479px): vertical stack, fire-once reveal on scroll
  ───────────────────────────────────────── */
  function setupMobileFallback() {
    slideRefs.current.forEach((el) => {
      if (!el) return;
      const texts = el.querySelectorAll(".h-slide__claim, .h-slide__word, .h-slide__label");
      texts.forEach((t) => {
        lineReveal(t as HTMLElement, {
          y: "140%",
          rot: 2.5,
          dur: 0.7,
          stagger: 0.05,
          start: "top 80%",
        });
      });
    });
  }

  /* ─────────────────────────────────────────
     DESKTOP path — full Tiwis choreography
  ───────────────────────────────────────── */
  function setupDesktop() {
    if (!sectionRef.current) return;

    // We need to reach outside the scope for the text pin (it's a sibling div
    // of horizontal-section, not inside sectionRef). That's fine — sectionRef
    // scope only controls cleanup; we'll clean up the text pin ST manually.
    const section = sectionRef.current.querySelector<HTMLElement>(".horizontal-section");
    const wrapper = sectionRef.current.querySelector<HTMLElement>(".horizontal-wrapper");
    const track = sectionRef.current.querySelector<HTMLElement>(".track");
    const textPin = textPinRef.current;

    if (!section || !wrapper || !track) return;

    const dist = () => track.scrollWidth - window.innerWidth;

    gsap.set(wrapper, { scale: 0, x: 0, transformOrigin: "100% 100%" });
    gsap.set(track, { x: 0 });

    /* ── Prepare reveals for all slides ──── */
    prepareSlideReveals();

    /* ── Master timeline ─────────────────── */
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
      // PHASE 1 (30%): grow wrapper from bottom-right corner
      .to(wrapper, { scale: 1, x: "50vw", duration: 0.3 })
      // Fire first card reveal at end of scale phase (claim + label + word)
      .call(
        () => {
          firstCardTweenRef.current?.play();
          const first = slideRefs.current[0];
          if (first) {
            const label = first.querySelector<HTMLElement>(".h-slide__label");
            const word = first.querySelector<HTMLElement>(".h-slide__word");
            if (label)
              gsap.to(label, { opacity: 0.55, duration: 0.5, ease: "power3.out", delay: 0.1 });
            if (word)
              gsap.to(word, {
                y: "0%",
                opacity: 1,
                duration: 0.9,
                ease: "power3.out",
                delay: 0.15,
              });
          }
        },
        undefined,
        ">",
      )
      .addLabel("scaleEnd")
      // PHASE 2 (20%): settle wrapper to x:0
      .to(wrapper, { x: "0vw", duration: 0.2 })
      // PHASE 3 (50%): horizontal travel
      .to(track, { x: () => -dist(), duration: 0.5 })
      // PHASE 4 (15%): exit hold
      .to({}, { duration: 0.15 });

    /* ── Secondary text pin ──────────────── */
    if (textPin) {
      ScrollTrigger.create({
        trigger: section,
        start: "top 20%",
        end: () => {
          const st = tl.scrollTrigger;
          if (!st) return "+=0";
          const s = st.start + tl.labels.scaleStart * (st.end - st.start);
          const e = st.start + tl.labels.scaleEnd * (st.end - st.start);
          return s + (e - s) * 0.7;
        },
        pin: textPin,
        pinSpacing: false,
        scrub: true,
        anticipatePin: 1,
      });
    }

    /* ── IO-based reveals for slides 2-6 ─── */
    setupIntersectionObserver();

    /* ── Intro reveals: están above-the-fold → disparan ON LOAD (como el hero
       de tiwis). Un ScrollTrigger clampeado a 0 nunca cruza su umbral si la
       página arranca quieta en y=0. ── */
    if (introRef.current) {
      const hairline = introRef.current.querySelector<HTMLElement>(".hl-intro__hairline");
      const manifesto = introRef.current.querySelector<HTMLElement>(".hl-intro__manifesto");
      if (hairline)
        gsap.to(hairline, { width: "100%", duration: 1.2, ease: "power3.inOut", delay: 0.25 });
      if (manifesto) {
        const t = lineReveal(manifesto, {
          y: "150%",
          rot: 2.5,
          dur: 1.2,
          stagger: 0.15,
          immediate: true,
        });
        gsap.delayedCall(0.1, () => t.play());
      }
    }

    /* ── Exit section reveals ─────────────── */
    if (exitRef.current) {
      const hairline = exitRef.current.querySelector<HTMLElement>(".hl-exit__hairline");
      const heading = exitRef.current.querySelector<HTMLElement>(".hl-exit__heading");
      const body = exitRef.current.querySelector<HTMLElement>(".hl-exit__body");
      if (hairline) hairlineReveal(hairline, "clamp(top 85%)");
      if (heading) lineReveal(heading, { y: "150%", rot: 2.5, dur: 1.2, stagger: 0.15 });
      if (body)
        lineReveal(body, { y: "150%", rot: 2.5, dur: 1.2, stagger: 0.1, start: "clamp(top 80%)" });
    }
  }

  /* ─────────────────────────────────────────
     Prepare (hide) all slide content before reveals fire
  ───────────────────────────────────────── */
  function prepareSlideReveals() {
    slideRefs.current.forEach((el, i) => {
      if (!el) return;

      const isCard = i % 2 === 0; // 0,2,4 = cards; 1,3,5 = spacers
      if (isCard) {
        const claim = el.querySelector<HTMLElement>(".h-slide__claim");
        const label = el.querySelector<HTMLElement>(".h-slide__label");
        const word = el.querySelector<HTMLElement>(".h-slide__word");

        if (i === 0) {
          // First card: gated — create paused tweens driven by tl.call
          if (claim) {
            const t = lineReveal(claim, {
              y: "140%",
              rot: 0,
              dur: 0.7,
              stagger: 0.05,
              immediate: true,
            });
            firstCardTweenRef.current = t;
          }
          if (label) gsap.set(label, { opacity: 0 });
          if (word) gsap.set(word, { y: "140%", opacity: 0 });
          // Animate label + word alongside the first reveal (fire from tl.call context)
          // We store them on the element for the call callback to find
          el.dataset.firstCard = "1";
        } else {
          // Cards 2 & 3: IO-based — partir YA y esconder las LÍNEAS dentro de
          // sus máscaras (esconder el párrafo padre lo dejaba invisible para
          // siempre: el reveal solo animaba las líneas internas).
          if (claim) {
            const split = SplitText.create(claim, { type: "lines", mask: "lines" });
            gsap.set(split.lines, { y: "140%" });
            claimSplitsRef.current.set(i, split);
          }
          if (label) gsap.set(label, { opacity: 0 });
          if (word) gsap.set(word, { y: "140%", opacity: 0 });
        }
      } else {
        // Spacer: prep SVG path
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

  /* ─────────────────────────────────────────
     IntersectionObserver — fires reveals on
     slides 2-6 (index 1-5); first card (0) is
     gated by tl.call above.
  ───────────────────────────────────────── */
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
      if (!el || i === 0) return; // skip first card (gated)
      el.dataset.slideIndex = String(i);
      observer.observe(el);
    });
  }

  function revealSlide(idx: number) {
    const el = slideRefs.current[idx];
    if (!el) return;
    const isCard = idx % 2 === 0;

    if (isCard) {
      const label = el.querySelector<HTMLElement>(".h-slide__label");
      const word = el.querySelector<HTMLElement>(".h-slide__word");

      const split = claimSplitsRef.current.get(idx);
      if (split) {
        gsap.to(split.lines, { y: "0%", duration: 0.7, ease: "power3.out", stagger: 0.05 });
      }
      if (label) {
        gsap.to(label, { opacity: 0.55, duration: 0.5, ease: "power3.out", delay: 0.1 });
      }
      if (word) {
        gsap.to(word, { y: "0%", opacity: 1, duration: 0.9, ease: "power3.out", delay: 0.15 });
      }
    } else {
      // Spacer slide
      const paths = el.querySelectorAll<SVGGeometryElement>(
        ".slide-side__svg path, .slide-side__svg circle, .slide-side__svg line, .slide-side__svg polyline",
      );
      paths.forEach((p, pi) => {
        gsap.to(p, {
          strokeDashoffset: 0,
          duration: 1.5,
          ease: "power3.inOut",
          delay: pi * 0.1,
        });
      });
      const label = el.querySelector<HTMLElement>(".slide-side__label");
      if (label) {
        gsap.to(label, { opacity: 0.65, y: "0px", duration: 0.7, ease: "power3.out", delay: 0.3 });
      }
    }
  }

  /* ─────────────────────────────────────────
     First-card gated reveal (called from tl.call)
  ───────────────────────────────────────── */
  useEffect(() => {
    // Nothing to set up here — the tl.call fires firstCardTweenRef.current.play()
    // and that tween was created inside useGSAP scope. Label + word are handled
    // as a supplemental reveal via revealSlide(0) called right after tl.call.
    // We wire that by patching the first card with a slight overlap:
    // The `firstCardTweenRef` holds the claim tween; label+word are fired from
    // the call-added callback in useGSAP. Nothing additional needed here.
  }, []);

  /* ─────────────────────────────────────────
     Slide ref assignment helper
  ───────────────────────────────────────── */
  function setSlideRef(idx: number) {
    return (el: HTMLDivElement | null) => {
      slideRefs.current[idx] = el;
    };
  }

  /* ─────────────────────────────────────────
     Render
  ───────────────────────────────────────── */
  return (
    <>
      {/* Outer wrapper that useGSAP uses as its scope root */}
      <div ref={sectionRef}>
        {/* ── Intro spacer + manifesto text ──────── */}
        <section className="hl-intro" ref={introRef} aria-label="Introducción">
          <div className="hl-intro__inner">
            <p className="hl-intro__eyebrow">Lab · Scroll horizontal</p>
            <span className="hl-intro__hairline" aria-hidden="true" />
            <h1 className="hl-intro__manifesto">
              Un asistente que conoce tu mundo, no solo tus tareas.
            </h1>
          </div>
        </section>

        {/* ── Text pin block (pinned while horizontal stage scales in) ── */}
        <div className="hl-text-pin" ref={textPinRef}>
          <p className="hl-text-pin__label">Lo que Ynara hace por vos</p>
          <p className="hl-text-pin__text">Tres pilares que se mueven con vos, no contra vos.</p>
        </div>

        {/* ── Horizontal section ──────────────────────── */}
        <div className="horizontal-section">
          <div className="horizontal-wrapper">
            <div className="track">
              {/* Card 0 — Productividad (first, gated reveal) */}
              <div className="h-slide" ref={setSlideRef(0)}>
                <div className="h-slide__top">
                  <p className="h-slide__claim">{CARDS[0].claim}</p>
                </div>
                <div className="h-slide__bot">
                  <span className="h-slide__label">{CARDS[0].label}</span>
                  <h2 className="h-slide__word">{CARDS[0].word}</h2>
                </div>
              </div>

              {/* Spacer 0 */}
              <div className="h-slide side" ref={setSlideRef(1)}>
                <div className="slide-side__content">
                  <span className="slide-side__label">{SPACERS[0].label}</span>
                  <SvgOrbit className="slide-side__svg" />
                </div>
              </div>

              {/* Card 1 — Memoria */}
              <div className="h-slide" ref={setSlideRef(2)}>
                <div className="h-slide__top">
                  <p className="h-slide__claim">{CARDS[1].claim}</p>
                </div>
                <div className="h-slide__bot">
                  <span className="h-slide__label">{CARDS[1].label}</span>
                  <h2 className="h-slide__word">{CARDS[1].word}</h2>
                </div>
              </div>

              {/* Spacer 1 */}
              <div className="h-slide side" ref={setSlideRef(3)}>
                <div className="slide-side__content">
                  <span className="slide-side__label">{SPACERS[1].label}</span>
                  <SvgPulse className="slide-side__svg" />
                </div>
              </div>

              {/* Card 2 — Bienestar */}
              <div className="h-slide" ref={setSlideRef(4)}>
                <div className="h-slide__top">
                  <p className="h-slide__claim">{CARDS[2].claim}</p>
                </div>
                <div className="h-slide__bot">
                  <span className="h-slide__label">{CARDS[2].label}</span>
                  <h2 className="h-slide__word">{CARDS[2].word}</h2>
                </div>
              </div>

              {/* Spacer 2 */}
              <div className="h-slide side" ref={setSlideRef(5)}>
                <div className="slide-side__content">
                  <span className="slide-side__label">{SPACERS[2].label}</span>
                  <SvgNet className="slide-side__svg" />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Exit section (ivory, wipes over the pinned stage) ────── */}
        <section className="hl-exit" ref={exitRef} aria-label="Cierre">
          <div className="hl-exit__inner">
            <p className="hl-exit__eyebrow">Ynara · 2026</p>
            <span className="hl-exit__hairline" aria-hidden="true" />
            <h2 className="hl-exit__heading">Tu contexto, siempre presente.</h2>
            <p className="hl-exit__body">
              Ynara no es otro app de notas. Es la presencia que aprende tu ritmo y te cuida el foco
              — para que el trabajo no te consuma.
            </p>
          </div>
        </section>
      </div>
    </>
  );
}
