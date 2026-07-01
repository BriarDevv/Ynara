import { Slide01 } from "./Slide01";
import { Slide02 } from "./Slide02";
import { Slide03 } from "./Slide03";
import { Slide04 } from "./Slide04";
import { Slide05 } from "./Slide05";
import { Slide06a } from "./Slide06a";
import { Slide06b } from "./Slide06b";
import { Slide07 } from "./Slide07";
import { Slide10 } from "./Slide10";
import { Slide11 } from "./Slide11";
import { Slide13 } from "./Slide13";
import { Slide14 } from "./Slide14";
import { Slide15 } from "./Slide15";
import { Slide16 } from "./Slide16";
import { Slide17 } from "./Slide17";
import { Slide18 } from "./Slide18";
import { SlideDia1 } from "./SlideDia1";
import { SlideDia2 } from "./SlideDia2";
import { SlideGracias } from "./SlideGracias";
import { SlideLanzEquipo } from "./SlideLanzEquipo";
import { SlideLanzEscenario } from "./SlideLanzEscenario";
import { SlideLanzFolleteria } from "./SlideLanzFolleteria";
import { SlideLanzPiezas } from "./SlideLanzPiezas";
import { SlideLanzStand } from "./SlideLanzStand";
import { SlideObjetos2 } from "./SlideObjetos2";
import { SlideObjetos3 } from "./SlideObjetos3";
import { SlideRedes2 } from "./SlideRedes2";
import { SlideVia2 } from "./SlideVia2";

/**
 * Las 28 láminas EN ORDEN (la posición acá ES el índice de cada lámina:
 * la página pasa `index={i}` y cada lámina lee su meta de DECK_SLIDES[i]).
 * Para reordenar/insertar, tocá solo este array y DECK_SLIDES — nada más.
 *
 * Slide08 ("tres pilares") y Slide09 ("la app") se sacaron del deck a pedido
 * de Mateo — quedan sus archivos borrados, no solo fuera de este array.
 */
export const SLIDES = [
  Slide01, // 01 · Presentarnos — portada
  Slide02, // 02 · Presentarnos — qué es Ynara
  Slide04, // 03 · El problema — ocho apps
  Slide03, // 04 · Storytelling — un día
  SlideDia1, // 05 · Storytelling — imagen 1
  SlideDia2, // 06 · Storytelling — imagen 2
  Slide05, // 07 · Desarrollo de la marca — calma en el caos
  Slide06a, // 08 · Desarrollo de la marca — nombre e isotipo (campo vivo)
  Slide06b, // 09 · Desarrollo de la marca — tipografía y color (campo vivo)
  Slide07, // 10 · Landing page
  Slide10, // 11 · Monetización — planes
  Slide11, // 12 · Monetización — viabilidad
  SlideLanzPiezas, // 13 · Lanzamiento — piezas físicas (señalética · afiche · roll-up)
  SlideLanzFolleteria, // 14 · Lanzamiento — folletería
  SlideLanzStand, // 15 · Lanzamiento — el stand
  SlideLanzEquipo, // 16 · Lanzamiento — el equipo acreditado
  SlideObjetos2, // 17 · Promoción — merch: remera (+ lapicera)
  SlideObjetos3, // 18 · Promoción — merch: buzo (+ tote)
  Slide16, // 19 · Promoción — resto de objetos (3 renders)
  SlideLanzEscenario, // 20 · Lanzamiento — el escenario
  Slide13, // 21 · Lanzamiento — la demo
  Slide14, // 22 · Promoción — redes (1/2)
  SlideRedes2, // 23 · Promoción — redes (2/2)
  Slide15, // 24 · Promoción — vía pública (1/2)
  SlideVia2, // 25 · Promoción — vía pública (2/2)
  Slide17, // 26 · Próximas funcionalidades — roadmap
  Slide18, // 27 · Cierre
  SlideGracias, // 28 · Cierre — gracias (logo grande + nombres)
] as const;
