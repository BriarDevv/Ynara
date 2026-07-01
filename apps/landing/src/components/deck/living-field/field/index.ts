/**
 * `living-field/field` — modelo compartido del **campo vivo** de la app Ynara
 * (DESIGN.md §2), portado al deck. Matemática pura + tipos (sin DOM/React): el
 * renderer Canvas2D (`LivingField.tsx`) traduce estos specs a llamadas de dibujo.
 */
export {
  dotColor,
  hexToRgb,
  type Mode,
  MODE_CLIMATE,
  type ModeClimate,
  type Rgb,
} from "./climate";
export {
  DENSITY_FACTOR,
  diamondCount,
  FIELD,
  type FieldDensity,
  LINK2,
  type LivingFieldVariant,
  MASKS,
  nodeCount,
  PR2,
  VARIANTS,
  type VariantConfig,
} from "./config";
export {
  advanceTime,
  type BloomSpec,
  breath,
  buildBlooms,
  buildWaves,
  type FieldDiamond,
  type FieldGeometry,
  type FieldNode,
  linkAlpha,
  nodeTwinkle,
  RIBBON_STEP,
  RIBBONS,
  type RibbonSpec,
  type Rng,
  repel,
  ribbonEdgeY,
  seedField,
  stepDiamonds,
  stepNodes,
  THREAD_STEP,
  THREADS,
  type ThreadSpec,
  threadY,
} from "./model";
