// @ynara/ui — fundaciones de UI compartibles web/mobile (ver README).
// Barrel público del package.

// Sistema gráfico "Red de memoria" + grano (DESIGN.md §2 / §3.6).
export type {
  FieldDensity,
  FieldLink,
  FieldNode,
  GrainOverlayProps,
  MemoryFieldGeometry,
  MemoryFieldProps,
} from "./graphics";
export { buildMemoryField, GrainOverlay, MemoryField } from "./graphics";
export type { IconName, IconProps, IconShape } from "./icons";
// Set de iconografía propia (DESIGN.md §9).
export { ICON_NAMES, ICON_SHAPES, Icon } from "./icons";
