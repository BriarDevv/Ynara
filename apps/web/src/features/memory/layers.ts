import type { MemoryLayer } from "@ynara/shared-schemas";
import type { IconName } from "@ynara/ui";

/**
 * Metadata de presentación de las 3 capas de memoria. El backend las nombra en
 * inglés técnico (`semantic`/`episodic`/`procedural`); para el usuario usamos
 * etiquetas cálidas en rioplatense (regla #9) que traducen el concepto, no la
 * implementación. El ícono sale del set propio (DESIGN §9), nunca un emoji.
 */
export type LayerDescriptor = {
  id: MemoryLayer;
  /** Etiqueta corta para chips y badges. */
  label: string;
  /** Frase que explica qué guarda la capa, para filtros y vacíos. */
  blurb: string;
  icon: IconName;
  /**
   * Color del marcador de la capa (Diamond del timeline/búsqueda), como el
   * mockup tiñe cada fila por su tag. Token del palette de marca (AA-safe como
   * relleno de un marcador chico; el texto sigue en `--color-ink-*`). Se tipa
   * como `var(--color-*)` para blindar contra hex hardcodeado.
   */
  color: `var(--color-${string})`;
};

export const MEMORY_LAYERS: readonly LayerDescriptor[] = [
  {
    id: "semantic",
    label: "Hechos",
    blurb: "Lo que Ynara sabe de vos",
    icon: "idea",
    color: "var(--color-celeste)",
  },
  {
    id: "episodic",
    label: "Momentos",
    blurb: "Lo que fue pasando",
    icon: "dialogo",
    color: "var(--color-violeta)",
  },
  {
    id: "procedural",
    label: "Costumbres",
    blurb: "Cómo te gusta trabajar",
    icon: "adaptacion",
    color: "var(--color-violaceo)",
  },
] as const;

export const LAYER_BY_ID: Record<MemoryLayer, LayerDescriptor> = MEMORY_LAYERS.reduce(
  (acc, layer) => {
    acc[layer.id] = layer;
    return acc;
  },
  {} as Record<MemoryLayer, LayerDescriptor>,
);
