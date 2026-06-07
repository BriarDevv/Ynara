import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";

/**
 * Punto único de entrada de GSAP: el wiring del motion (DESIGN.md §8.4) al
 * servicio de los momentos-firma de marca (§8.3 / §16 #7).
 *
 * Registramos `useGSAP` **una sola vez** acá (patrón oficial de GreenSock para
 * React): `registerPlugin` le da al hook el handle de **esta** instancia de
 * `gsap` (lo que importa con múltiples instancias / SSR) y centraliza el wiring
 * — cualquier import de gsap/useGSAP en la app sale de este módulo, no de los
 * paquetes directos.
 *
 * GSAP queda reservado para **secuencias / momentos-firma** (entrada del hero,
 * reveal del recap), nunca para micro-interacciones — eso vive en CSS keyframes
 * (§8.2). Todo lo que anime debe gatearse por reduced-motion (`gsap.matchMedia`
 * + el override del store de a11y); ver `HeroReveal`.
 */
gsap.registerPlugin(useGSAP);

export { gsap, useGSAP };
