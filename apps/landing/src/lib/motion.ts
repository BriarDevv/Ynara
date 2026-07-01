"use client";

import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";

let registered = false;

/** Registra ScrollTrigger + SplitText una sola vez, client-side. */
export function registerGsap() {
  if (registered || typeof window === "undefined") return;
  gsap.registerPlugin(ScrollTrigger, SplitText);
  registered = true;
}

/** ¿El usuario pidió menos movimiento? Siempre respetar. */
export function reducedMotion(): boolean {
  return (
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

// Vocabulario de easing único — mismas curvas en todas las secciones.
export const EASE = "power3.out";
export const EASE_EXPO = "expo.out";
export const EASE_INOUT = "power2.inOut";

export { gsap, ScrollTrigger, SplitText, useGSAP };
