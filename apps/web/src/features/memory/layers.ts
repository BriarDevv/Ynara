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
};

export const MEMORY_LAYERS: readonly LayerDescriptor[] = [
  {
    id: "semantic",
    label: "Hechos",
    blurb: "Lo que Ynara sabe de vos",
    icon: "idea",
  },
  {
    id: "episodic",
    label: "Momentos",
    blurb: "Lo que fue pasando",
    icon: "dialogo",
  },
  {
    id: "procedural",
    label: "Costumbres",
    blurb: "Cómo te gusta trabajar",
    icon: "adaptacion",
  },
] as const;

export const LAYER_BY_ID: Record<MemoryLayer, LayerDescriptor> = MEMORY_LAYERS.reduce(
  (acc, layer) => {
    acc[layer.id] = layer;
    return acc;
  },
  {} as Record<MemoryLayer, LayerDescriptor>,
);
