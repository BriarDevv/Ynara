"use client";

import Lenis from "lenis";
import { useEffect } from "react";
import { gsap, reducedMotion, registerGsap, ScrollTrigger } from "@/lib/motion";
import { useIsDeckRoute } from "@/lib/useDeckRoute";

declare global {
  interface Window {
    __lenis?: Lenis;
    __ynaraIntroDone?: boolean;
  }
}

/**
 * Smooth scroll Lenis sincronizado con GSAP ScrollTrigger.
 * Si va a correr el preloader (intro no vista y sin reduced-motion), arranca
 * en estado detenido — el preloader lo libera al levantar el telón.
 */
export default function SmoothScroll() {
  const isDeck = useIsDeckRoute();
  useEffect(() => {
    if (isDeck) return; // el deck navega por teclado: nada de smooth-scroll
    if (reducedMotion()) return;
    registerGsap();

    const lenis = new Lenis({
      // Más corto (1.1 → 0.9): el smooth-scroll responde más rápido al gesto y
      // pelea menos con el scroll nativo del recién llegado (doble pin + wheel).
      duration: 0.9,
      easing: (t) => Math.min(1, 1.001 - 2 ** (-10 * t)),
      smoothWheel: true,
      touchMultiplier: 1.4,
    });
    window.__lenis = lenis;

    // Si el telón va a correr, no dejar scrollear hasta que termine.
    let introWillPlay = false;
    try {
      introWillPlay = sessionStorage.getItem("ynara-intro") !== "1";
    } catch {}
    if (introWillPlay && !window.__ynaraIntroDone) lenis.stop();

    lenis.on("scroll", ScrollTrigger.update);

    const raf = (time: number) => lenis.raf(time * 1000);
    gsap.ticker.add(raf);
    gsap.ticker.lagSmoothing(0);
    document.documentElement.classList.add("lenis");

    // COORDINACIÓN: re-medir TODOS los ScrollTriggers (reveals, el pin
    // horizontal y el endY del campo) contra el layout FINAL — después de que
    // las fuentes ajustan las alturas del texto y el canvas montó. Sin esto las
    // posiciones se calculan contra un layout a medio asentar y los reveals/pin
    // quedan corridos. Varios refreshes cubren mounts/fuentes/imagenes tardías.
    const refresh = () => {
      lenis.resize();
      ScrollTrigger.refresh();
    };
    const settleTimers = [window.setTimeout(refresh, 350), window.setTimeout(refresh, 1200)];
    document.fonts?.ready?.then(refresh).catch(() => {});
    window.addEventListener("load", refresh);

    // Anclas in-page → scroll suave con Lenis, aterrizando DESPUÉS del wipe de la
    // sección (si lo tiene) para no caer en el panel de transición vacío.
    const onAnchorClick = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey) return;
      const a = (e.target as HTMLElement | null)?.closest?.(
        'a[href^="#"]',
      ) as HTMLAnchorElement | null;
      const id = a?.getAttribute("href")?.slice(1);
      if (!id) return; // ignora href="#" (placeholders)
      const target = document.getElementById(id);
      if (!target) return;
      e.preventDefault();
      const wipe = target.querySelector<HTMLElement>("[data-wipe]");
      lenis.scrollTo(target, { offset: wipe ? wipe.offsetHeight : 0 });
    };
    document.addEventListener("click", onAnchorClick);

    return () => {
      document.removeEventListener("click", onAnchorClick);
      window.removeEventListener("load", refresh);
      settleTimers.forEach(clearTimeout);
      gsap.ticker.remove(raf);
      lenis.destroy();
      window.__lenis = undefined;
      document.documentElement.classList.remove("lenis");
    };
  }, [isDeck]);

  return null;
}
