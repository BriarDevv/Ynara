/**
 * Modos del onboarding (mobile) — re-export de la fuente única en
 * `@/components/ui/modes`, que comparten onboarding y chat. Se mantiene el
 * nombre `MODE_OPTIONS` por compatibilidad con `ModesStep`.
 */

/** Modo pre-marcado por default en el step de modos — fuente única en core. */
export { DEFAULT_MODE } from "@ynara/core/features/modes";
export { MODE_DESCRIPTORS as MODE_OPTIONS, MODE_DOT_CLASS } from "@/components/ui/modes";
