import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";

/**
 * Punto único de entrada de GSAP (DESIGN.md §8.4 / §16 #7).
 *
 * Registramos `useGSAP` **una sola vez** acá: además de ser la guía oficial de
 * GreenSock para React, el `registerPlugin` evita que el tree-shaking descarte
 * el hook y centraliza el wiring (cualquier import de gsap/useGSAP en la app
 * sale de este módulo, no de los paquetes directos).
 *
 * GSAP queda reservado para **secuencias / momentos-firma** (entrada del hero,
 * reveal del recap), nunca para micro-interacciones — eso vive en CSS keyframes
 * (§8.2). Todo lo que anime debe gatearse por reduced-motion (`gsap.matchMedia`
 * + el override del store de a11y); ver `HeroReveal`.
 */
gsap.registerPlugin(useGSAP);

export { gsap, useGSAP };
