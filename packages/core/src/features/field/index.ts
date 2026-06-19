/**
 * `@ynara/core/features/field` — modelo compartido del **campo vivo** (DESIGN.md
 * §2). Fuente única para los dos renderers: web (`LivingField`, Canvas2D) y
 * mobile (Skia). Acá vive TODO lo que define cómo se ve y se mueve el fondo
 * (clima, config por variante, geometría, animación, specs de blooms/ondas);
 * cada plataforma sólo traduce estos specs a sus llamadas de dibujo, así el
 * fondo queda idéntico en web y mobile.
 *
 * No exporta nada de DOM/React: es matemática pura + tipos.
 */
export { dotColor, hexToRgb, MODE_CLIMATE, type ModeClimate, type Rgb } from "./climate";
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
