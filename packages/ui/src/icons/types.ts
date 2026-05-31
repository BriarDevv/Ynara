// Tipos del set de íconos propio de Ynara (DESIGN.md §9).
//
// La geometría se modela como **data** (no como JSX) a propósito: es la
// capa portable web/mobile. El renderer web (`Icon.tsx`) la mapea a
// `<svg>`; un renderer RN futuro mapea las mismas formas a
// `react-native-svg` (`<Svg>`/`<Circle>`/`<Rect>`/`<Path>`) sin tocar la
// geometría.

/** Nombres del set. Español, fiel a las etiquetas de la guía de marca §9. */
export type IconName =
  // Set de marca (geometría literal de la guía de identidad visual).
  | "idea"
  | "conexion"
  | "memoria"
  | "nota"
  | "buscar"
  | "dialogo"
  | "recordatorio"
  | "adaptacion"
  | "foco"
  | "red"
  // Utilitarios (mismo trazo y grilla que el set de marca).
  | "enviar"
  | "detener"
  | "atras"
  | "cerrar"
  | "chevron";

/**
 * Primitivas de dibujo. Todas se trazan (stroke), nunca se rellenan: el
 * "trazo uniforme" del §9 sale de un único `stroke-width` en el renderer.
 * Coordenadas en la grilla de `44×44` de la guía de marca.
 */
export type IconShape =
  | { type: "circle"; cx: number; cy: number; r: number }
  | {
      type: "rect";
      x: number;
      y: number;
      w: number;
      h: number;
      rx?: number;
      /** Rotación en grados alrededor del centro del rect (ej: diamante). */
      rotate?: number;
    }
  | { type: "path"; d: string };

export type IconProps = {
  name: IconName;
  /** Lado del cuadro en px. Default 24. El trazo es uniforme a cualquier tamaño. */
  size?: number;
  /** Grosor del trazo en unidades de la grilla 44. Default 2.2 (valor de marca). */
  strokeWidth?: number;
  /** Color del trazo. Default `currentColor` (hereda el color de texto / token). */
  color?: string;
  className?: string;
  /**
   * Etiqueta accesible. Si se omite, el ícono es decorativo
   * (`aria-hidden`); si se pasa, expone `role="img"` + `aria-label`.
   */
  title?: string;
};
