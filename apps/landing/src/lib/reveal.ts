"use client";

import { gsap, reducedMotion, registerGsap, type ScrollTrigger, SplitText } from "@/lib/motion";

export interface LineRevealOpts {
  /** Starting vertical offset — defaults to tiwis "manifesto" value */
  y?: string;
  /** Starting rotation in degrees */
  rot?: number;
  /** Duration in seconds */
  dur?: number;
  /** Stagger amount (total time spread across all lines) */
  stagger?: number;
  /** ScrollTrigger start string — defaults to "clamp(top 85%)" */
  start?: string;
  /** If true, returns the tween without a ScrollTrigger (caller drives it) */
  immediate?: boolean;
}

/**
 * Tiwis-signature SplitText line-mask reveal.
 *
 * Creates a SplitText instance on `el`, sets each line to the "behind the
 * mask" starting state, then either:
 *   - attaches a ScrollTrigger (default) so it fires at `start`, or
 *   - returns a paused tween (immediate:true) for caller-driven playback.
 *
 * Returns the GSAP tween so callers can chain `.play()` / `.kill()`.
 *
 * @example
 *   // Standard scroll-triggered reveal
 *   lineReveal(headingEl);
 *
 *   // Manual / timeline-gated reveal (first card)
 *   const tween = lineReveal(firstCardEl, { immediate: true });
 *   tween.play();
 */
export function lineReveal(el: Element, opts: LineRevealOpts = {}) {
  const {
    y = "150%",
    rot = 2.5,
    dur = 1.2,
    stagger = 0.15,
    start = "clamp(top 85%)",
    immediate = false,
  } = opts;

  registerGsap();

  // Reduced-motion (defensa en profundidad): split sólo si hace falta para no
  // romper el layout, dejá las líneas en su estado FINAL visible y devolvé un
  // tween ya completado (compatible con callers que hacen .play()).
  if (reducedMotion()) {
    const split = SplitText.create(el, { type: "lines", mask: "lines" });
    gsap.set(split.lines, { y: "0%", rotation: 0, opacity: 1 });
    const tween = gsap.to(split.lines, { y: "0%", rotation: 0, duration: 0 });
    tween.progress(1).pause();
    return tween;
  }

  // Immediate (caller-driven, on-load): split una vez, tween pausado.
  if (immediate) {
    const split = SplitText.create(el, { type: "lines", mask: "lines" });
    gsap.set(split.lines, { y, rotation: rot, opacity: 1 });
    const tween = gsap.to(split.lines, {
      y: "0%",
      rotation: 0,
      duration: dur,
      ease: "power3.inOut",
      stagger: { amount: stagger },
    });
    tween.pause(0);
    return tween;
  }

  // Scroll-triggered: `autoSplit` re-divide las líneas cuando cargan las fuentes
  // o cambia el ancho; `onSplit` re-arma el reveal sobre las líneas nuevas. Sin
  // esto, tras un resize/font-swap las máscaras conservan el corte viejo y el
  // texto se clippea al revelarse (hallazgo de la auditoría — alto impacto).
  let tween: gsap.core.Tween | undefined;
  SplitText.create(el, {
    type: "lines",
    mask: "lines",
    autoSplit: true,
    onSplit: (self: SplitText) => {
      gsap.set(self.lines, { y, rotation: rot, opacity: 1 });
      tween = gsap.to(self.lines, {
        y: "0%",
        rotation: 0,
        duration: dur,
        ease: "power3.inOut",
        stagger: { amount: stagger },
        scrollTrigger: { trigger: el, start } satisfies ScrollTrigger.Vars,
      });
      return tween;
    },
  } as SplitText.Vars);
  return tween as gsap.core.Tween;
}

/**
 * Animates a hairline (1px rule) from width 0 → 100%.
 * Tiwis timing: 1.2s power3.inOut, scroll-triggered at top 85%.
 */
export function hairlineReveal(el: HTMLElement, start = "clamp(top 85%)"): gsap.core.Tween {
  registerGsap();
  // Reduced-motion: hairline en su estado final (100%), tween no-op.
  if (reducedMotion()) {
    gsap.set(el, { width: "100%" });
    return gsap.to(el, { width: "100%", duration: 0 });
  }
  gsap.set(el, { width: "0%" });
  return gsap.to(el, {
    width: "100%",
    duration: 1.2,
    ease: "power3.inOut",
    scrollTrigger: { trigger: el, start } satisfies ScrollTrigger.Vars,
  });
}

/**
 * SVG stroke-draw reveal: sets strokeDasharray + strokeDashoffset to the path
 * total length, then animates dashoffset → 0.
 */
export function svgDrawReveal(
  path: SVGPathElement | SVGGeometryElement,
  opts: { dur?: number; ease?: string; delay?: number } = {},
): gsap.core.Tween {
  registerGsap();
  const { dur = 1.5, ease = "power3.inOut", delay = 0 } = opts;
  const len = path.getTotalLength();
  // Reduced-motion: trazo completo (dashoffset 0), tween no-op.
  if (reducedMotion()) {
    gsap.set(path, { strokeDasharray: len, strokeDashoffset: 0 });
    return gsap.to(path, { strokeDashoffset: 0, duration: 0 });
  }
  gsap.set(path, { strokeDasharray: len, strokeDashoffset: len });
  return gsap.to(path, {
    strokeDashoffset: 0,
    duration: dur,
    ease,
    delay,
  });
}
