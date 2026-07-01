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
import { SlideRedesAnsiedad } from "./SlideRedesAnsiedad";
import { SlideRedesAtencion } from "./SlideRedesAtencion";
import { SlideRedesHistoria } from "./SlideRedesHistoria";
import { SlideRedesTareas } from "./SlideRedesTareas";
import { SlideRedesTweet } from "./SlideRedesTweet";
import { SlideViaAfichePerdida } from "./SlideViaAfichePerdida";
import { SlideViaCartelCalle } from "./SlideViaCartelCalle";
import { SlideViaParadaColectivo } from "./SlideViaParadaColectivo";

/**
 * Las 32 láminas EN ORDEN (la posición acá ES el índice de cada lámina:
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
  SlideRedesAnsiedad, // 22 · Promoción — redes: post «Ansiedad de pestaña» (1/5)
  SlideRedesAtencion, // 23 · Promoción — redes: post «Atención fragmentada» (2/5)
  SlideRedesTareas, // 24 · Promoción — redes: post lista de tareas (3/5)
  SlideRedesTweet, // 25 · Promoción — redes: post formato tweet (4/5)
  SlideRedesHistoria, // 26 · Promoción — redes: historia, formato vertical (5/5)
  SlideViaCartelCalle, // 27 · Promoción — vía pública: cartel de calle (1/3)
  SlideViaParadaColectivo, // 28 · Promoción — vía pública: parada de colectivo (2/3)
  SlideViaAfichePerdida, // 29 · Promoción — vía pública: afiche «Perdida» (3/3)
  Slide17, // 30 · Próximas funcionalidades — roadmap
  Slide18, // 31 · Cierre
  SlideGracias, // 32 · Cierre — gracias (logo grande + nombres)
] as const;
