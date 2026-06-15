import type { Mode } from "@ynara/shared-schemas";

/**
 * Modos del onboarding (mobile) — re-export de la fuente única en
 * `@/components/ui/modes`, que comparten onboarding y chat. Se mantiene el
 * nombre `MODE_OPTIONS` por compatibilidad con `ModesStep`.
 */
export {
  MODE_DESCRIPTORS as MODE_OPTIONS,
  MODE_DOT_CLASS,
  type ModeDescriptor as ModeOption,
} from "@/components/ui/modes";

/** Modo pre-marcado por default en el step de modos (igual que la web). */
export const DEFAULT_MODE: Mode = "productividad";
