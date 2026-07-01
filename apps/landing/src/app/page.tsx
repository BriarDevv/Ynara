import { Closing } from "@/components/journey/Closing";
import { Hero } from "@/components/journey/Hero";
import { HorizontalModes } from "@/components/journey/HorizontalModes";
import { Marquee } from "@/components/journey/Marquee";
import { Problem } from "@/components/journey/Problem";
import { Trust } from "@/components/journey/Trust";
import { VoiceChapter } from "@/components/journey/VoiceChapter";

/**
 * EL VIAJE — un landing de producto sobre UN campo WebGL persistente (seda mate
 * estilo Tiwis) conducido por UN timeline maestro. Narrativa de conversión:
 *
 *   00 Hero        → qué es Ynara + el valor en una línea + CTA (olas).
 *   01 Problema    → el gancho: "Vivís entre ocho apps. Ynara es una." (giro cenital).
 *   02 Pilares     → lo que hace: scroll HORIZONTAL con las 3 cards (tablero→cards).
 *   03 Demo        → cómo se siente: chats reales (carbón).
 *   04 Privacidad  → tus datos son tuyos (carbón).
 *   05 Precio+CTA  → empezá gratis, sumate al acceso anticipado (ivory).
 */
export default function HomePage() {
  return (
    <>
      <Hero />
      <Problem />
      <HorizontalModes />
      <Marquee />
      <VoiceChapter />
      <Trust />
      <Closing />
    </>
  );
}
