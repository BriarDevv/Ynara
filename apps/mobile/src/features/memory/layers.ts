import type { MemoryLayer } from "@ynara/shared-schemas";

/**
 * Metadata de presentación de las 3 capas de memoria (mobile) — espejo de
 * `apps/web/src/features/memory/layers.ts`, sin el ícono de `@ynara/ui` (que
 * mobile no tiene): acá la capa se distingue por un dot de color de marca.
 * Etiquetas cálidas en rioplatense, no la jerga técnica del backend.
 */
export type LayerDescriptor = {
  id: MemoryLayer;
  label: string;
  blurb: string;
};

export const MEMORY_LAYERS: readonly LayerDescriptor[] = [
  { id: "semantic", label: "Hechos", blurb: "Lo que Ynara sabe de vos" },
  { id: "episodic", label: "Momentos", blurb: "Lo que fue pasando" },
  { id: "procedural", label: "Costumbres", blurb: "Cómo te gusta trabajar" },
] as const;

export const LAYER_BY_ID: Record<MemoryLayer, LayerDescriptor> = MEMORY_LAYERS.reduce(
  (acc, layer) => {
    acc[layer.id] = layer;
    return acc;
  },
  {} as Record<MemoryLayer, LayerDescriptor>,
);

/**
 * Dot de color por capa (clase estática NativeWind: el className tiene que ser
 * literal en build time). Tints de la paleta de marca.
 */
export const LAYER_DOT_CLASS: Record<MemoryLayer, string> = {
  semantic: "bg-azul",
  episodic: "bg-violeta",
  procedural: "bg-celeste",
};
